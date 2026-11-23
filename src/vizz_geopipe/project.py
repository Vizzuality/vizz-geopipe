"""A project: the layers of a repository and the destinations they publish to."""

import logging
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Literal

from vizz_geopipe.destinations import Destination
from vizz_geopipe.errors import GdalError
from vizz_geopipe.errors import PublishError
from vizz_geopipe.errors import SourceError
from vizz_geopipe.fingerprint import read_build
from vizz_geopipe.fingerprint import read_published
from vizz_geopipe.fingerprint import write_published
from vizz_geopipe.layers import Layer
from vizz_geopipe.workdir import Workdir
from vizz_geopipe.workdir import check_folder_name

logger = logging.getLogger(__name__)

# The errors a layer's step turns into a failed result. Not ``Exception``: a bug (a
# TypeError, a KeyError) must stop the run, not be filed as one more failed layer.
CAUGHT = (GdalError, SourceError, PublishError, ValueError)


@dataclass(frozen=True, kw_only=True)
class StepResult:
    """What happened to one layer in one step.

    Attributes:
        layer: The layer's name.
        step: Which step this is.
        outcome: What happened: ``built``, ``skipped``, ``published`` or ``failed``.
        destination: The destination's name, for a publish step.
        detail: The artifact path, the URI, or the error's message.
        error: The error, when the outcome is ``failed``.
    """

    layer: str
    step: Literal["build", "publish"]
    outcome: Literal["built", "skipped", "published", "failed"]
    destination: str | None = None
    detail: str | None = None
    error: Exception | None = None

    @property
    def failed(self) -> bool:
        """Whether the step failed."""
        return self.outcome == "failed"


@dataclass(frozen=True, kw_only=True)
class LayerStatus:
    """Where one layer stands: built or not, and published or not.

    Attributes:
        name: The layer's name.
        title: The layer's title.
        state: ``not built``, ``built``, ``stale`` (the sources changed since the build),
            or ``unknown`` (the sources could not be checked).
        published: For each destination the layer publishes to, whether the build on disk is
            ``published`` there, ``outdated`` (another build is) or ``not published``.
        detail: Why the state is ``unknown``.
    """

    name: str
    title: str
    state: Literal["not built", "built", "stale", "unknown"]
    published: Mapping[str, Literal["published", "outdated", "not published"]]
    detail: str | None = None


@dataclass(frozen=True, kw_only=True)
class Project:
    """The layers of a repository, the destinations they publish to, and where data lives.

    The configuration is checked when the project is created, so a mistake fails before
    anything is downloaded or built.

    Attributes:
        data_dir: The project's data folder.
        layers: The layers, in the order they are built and published.
        destinations: The destinations by name, as ``Layer.publish_to`` refers to them.
    """

    data_dir: Path
    layers: Sequence[Layer]
    destinations: Mapping[str, Destination] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Check the layers against each other and against the destinations.

        Raises:
            ValueError: If two layers share a name, a name is not a single folder name, a
                layer publishes to an unknown destination, or a destination cannot publish
                a layer's file or name.
        """
        seen = set()
        for layer in self.layers:
            if layer.name in seen:
                raise ValueError(f"two layers are named {layer.name!r}")
            seen.add(layer.name)
            try:
                check_folder_name(layer.name)
            except ValueError as error:
                raise ValueError(f"layer {layer.name!r}: {error}") from None
            for key in layer.publish_to:
                if key not in self.destinations:
                    raise ValueError(
                        f"layer {layer.name!r} publishes to {key!r}, which is not in destinations"
                    )
                try:
                    self._check_destination(layer, self.destinations[key])
                except ValueError as error:
                    raise ValueError(f"layer {layer.name!r}: {error}") from None

    def _check_destination(self, layer: Layer, destination: Destination) -> None:
        """Raise ``ValueError`` if ``destination`` cannot publish ``layer``."""
        if not destination.accepts(Path(f"{layer.name}{layer.suffix}")):
            raise ValueError(f"{type(destination).__name__} cannot publish {layer.suffix} files")
        destination.validate(layer.name)

    @property
    def workdir(self) -> Workdir:
        """The project's data folders."""
        return Workdir(self.data_dir)

    def _select(
        self, names: Sequence[str] | None, *, to: str | None = None, publishing: bool = False
    ) -> list[Layer]:
        """Return the layers a call works on, in declaration order.

        Args:
            names: The layers asked for, or ``None`` for all of them.
            to: Only the layers that publish to this destination. Layers named in ``names``
                are never filtered by it; with ``publishing`` they must publish to it, or
                the call raises.
            publishing: The call publishes, so every layer must have something to publish.

        Raises:
            ValueError: If a name or ``to`` is unknown, or a layer asked for by name has
                nothing to publish.
        """
        known = {layer.name for layer in self.layers}
        unknown = sorted(set(names or ()) - known)
        if unknown:
            raise ValueError(f"unknown layers: {', '.join(unknown)}")
        if to is not None and to not in self.destinations:
            raise ValueError(f"unknown destination: {to!r}")

        def publishes(layer: Layer) -> bool:
            return to in layer.publish_to if to is not None else bool(layer.publish_to)

        if names is None:
            filtered = publishing or to is not None
            return [layer for layer in self.layers if not filtered or publishes(layer)]
        chosen = [layer for layer in self.layers if layer.name in names]
        if publishing:
            for layer in chosen:
                if not publishes(layer):
                    raise ValueError(f"layer {layer.name!r} has nothing to publish")
        return chosen

    def _failed(
        self,
        layer: Layer,
        step: Literal["build", "publish"],
        error: Exception,
        destination: str | None = None,
    ) -> StepResult:
        """Log ``error`` and return it as the ``failed`` result of ``step`` for ``layer``."""
        if destination is None:
            logger.error("%s failed: %s", layer.name, error)
        else:
            logger.error("%s on %s failed: %s", layer.name, destination, error)
        return StepResult(
            layer=layer.name,
            step=step,
            outcome="failed",
            destination=destination,
            detail=str(error),
            error=error,
        )

    def build(
        self, names: Sequence[str] | None = None, *, refresh: bool = False, force: bool = False
    ) -> list[StepResult]:
        """Build the layers that need it, and carry on past one that fails.

        Args:
            names: The layers to build, or ``None`` for all of them.
            refresh: Download the sources again. This rebuilds too: downloading again and
                then skipping the build would change nothing.
            force: Build even if the layer is built and unchanged.

        Returns:
            One result per layer, in declaration order: ``built`` (``detail`` is the
            artifact), ``skipped`` or ``failed``.

        Raises:
            ValueError: If a name is unknown (before anything is built).
        """
        workdir = self.workdir
        results = []
        for layer in self._select(names):
            try:
                if not (force or refresh) and layer.is_built(workdir):
                    logger.info("Skipping %s: built and unchanged", layer.name)
                    results.append(StepResult(layer=layer.name, step="build", outcome="skipped"))
                    continue
                artifact = layer.build(workdir, refresh=refresh)
            except CAUGHT as error:
                results.append(self._failed(layer, "build", error))
            else:
                results.append(
                    StepResult(
                        layer=layer.name, step="build", outcome="built", detail=str(artifact)
                    )
                )
        return results

    def publish(
        self,
        names: Sequence[str] | None = None,
        *,
        to: str | None = None,
        force: bool = False,
    ) -> list[StepResult]:
        """Publish the built layers to their destinations, skipping what is already there.

        Each layer goes to every destination in its ``publish_to``, or only to ``to`` when
        given. A layer that is not built fails with a hint to build it. A layer whose
        sources changed since the build is published as built, with a warning. The
        destination records the build's fingerprint, so the next call skips it.

        Args:
            names: The layers to publish, or ``None`` for all that publish somewhere.
            to: Publish only to this destination.
            force: Publish even if this build is already published there.

        Returns:
            One result per layer and destination, in declaration order: ``published``
            (``detail`` is the URI), ``skipped`` or ``failed``.

        Raises:
            ValueError: If a name or ``to`` is unknown, or a layer asked for by name has
                nothing to publish (before anything is published).
        """
        layers = self._select(names, to=to, publishing=True)
        results = []
        for layer in layers:
            artifact = layer.artifact(self.workdir)
            build = read_build(artifact.parent) if artifact.is_file() else None
            keys = [to] if to is not None else list(layer.publish_to)
            if build is None:
                for key in keys:
                    error = PublishError(
                        type(self.destinations[key]).__name__,
                        f"{layer.name} is not built; run geopipe build {layer.name}",
                    )
                    results.append(self._failed(layer, "publish", error, destination=key))
                continue
            try:
                if layer.fingerprint() != build:
                    logger.warning(
                        "%s changed since it was built; publishing the existing build", layer.name
                    )
            except SourceError as error:
                logger.warning("could not check whether %s changed: %s", layer.name, error)
            for key in keys:
                if not force and read_published(artifact.parent, key) == build:
                    logger.info("Skipping %s on %s: already published", layer.name, key)
                    results.append(
                        StepResult(
                            layer=layer.name, step="publish", outcome="skipped", destination=key
                        )
                    )
                    continue
                destination = self.destinations[key]
                try:
                    uri = destination.publish(artifact, name=layer.name, title=layer.title)
                except CAUGHT as error:
                    results.append(self._failed(layer, "publish", error, destination=key))
                else:
                    write_published(artifact.parent, key, build, uri)
                    results.append(
                        StepResult(
                            layer=layer.name,
                            step="publish",
                            outcome="published",
                            destination=key,
                            detail=uri,
                        )
                    )
        return results

    def run(
        self,
        names: Sequence[str] | None = None,
        *,
        to: str | None = None,
        refresh: bool = False,
        force: bool = False,
        publish: bool = True,
    ) -> list[StepResult]:
        """Build the layers, then publish the ones that built.

        Args:
            names: The layers to run, or ``None`` for all (with ``to`` or ``publish``, all
                that publish, to ``to`` when given).
            to: Publish only to this destination.
            refresh: Download the sources again.
            force: Build and publish even if nothing changed.
            publish: Whether to publish after building.

        Returns:
            The build results, then the publish results.

        Raises:
            ValueError: If a name or ``to`` is unknown, or a layer asked for by name has
                nothing to publish (before any work).
        """
        selected = [layer.name for layer in self._select(names, to=to, publishing=publish)]
        results = self.build(selected, refresh=refresh, force=force)
        if publish:
            built = [r.layer for r in results if not r.failed]
            if built:
                results += self.publish(built, to=to, force=force)
        return results

    def status(self, names: Sequence[str] | None = None) -> list[LayerStatus]:
        """Say where each layer stands, without building or publishing anything.

        Args:
            names: The layers to report, or ``None`` for all of them.

        Returns:
            One status per layer, in declaration order.

        Raises:
            ValueError: If a name is unknown.
        """
        statuses = []
        for layer in self._select(names):
            artifact = layer.artifact(self.workdir)
            build = read_build(artifact.parent) if artifact.is_file() else None
            state, detail = "not built", None
            if build is not None:
                try:
                    state = "built" if layer.fingerprint() == build else "stale"
                except SourceError as error:
                    state, detail = "unknown", str(error)
            published = {}
            for key in layer.publish_to:
                recorded = read_published(artifact.parent, key)
                if recorded is None or build is None:
                    published[key] = "not published"
                else:
                    published[key] = "published" if recorded == build else "outdated"
            statuses.append(
                LayerStatus(
                    name=layer.name,
                    title=layer.title,
                    state=state,
                    published=published,
                    detail=detail,
                )
            )
        return statuses
