import json
import logging
from pathlib import Path
from typing import Union, Type, Optional
from zipfile import ZipFile

from amaze.simu import Robot
from amaze.simu.controllers.base import BaseController
from amaze.simu.controllers.keyboard import KeyboardController
from amaze.simu.controllers.random import RandomController
from amaze.simu.controllers.tabular import TabularController

logger = logging.getLogger(__name__)

CONTROLLERS = {
    "random": RandomController,
    "keyboard": KeyboardController,
    "tabular": TabularController
}


def check_types(controller: Type[BaseController],
                robot: Robot.BuildData) -> bool:
    """ Ensure that the controller is compatible with the specified
     inputs/outputs """
    assert robot.inputs in controller.inputs_types(), \
        (f"Input type {robot.inputs} is not valid for {controller}."
         f" Expected one of {controller.inputs_types()}")
    assert robot.outputs in controller.outputs_types(), \
        (f"Output type {robot.outputs} is not valid for {controller}."
         f" Expected {controller.outputs_types()}")
    return True


def controller_factory(c_type: str, c_data: dict):
    """ Create a controller of a given c_type from the given c_data """
    return CONTROLLERS[c_type.lower()](**c_data)


def save(controller: BaseController, path: Union[Path, str],
         infos: Optional[dict] = None):
    """ Save the controller under the provided path

    Optionally store the provided information for latter reference (e.g.
    type of mazes, performance, ...)
    """
    reverse_map = {t: n for n, t in CONTROLLERS.items()}
    assert type(controller) in reverse_map, \
        f"Unknown controller type {type(controller)}"
    controller_class = reverse_map[type(controller)]

    if path.suffix != ".zip":
        path = path.with_suffix(".zip")

    with ZipFile(path, "w") as archive:
        archive.writestr("controller_class", controller_class)
        controller.save_to_archive(archive)

        _infos = controller.infos.copy()
        _infos.update(infos)
        archive.writestr("infos",
                         json.dumps(_infos).encode("utf-8"))

    logger.debug(f"Saved controller to {path}")

    return path


def load(path: Union[Path, str]):
    """ Loads a controller from the provided path.

    Handles any type currently registered. When using extensions, make sure
    to load (import) all those used during training.
    """
    logger.debug(f"Loading controller from {path}")
    with ZipFile(path, "r") as archive:
        controller_class = archive.read("controller_class").decode("utf-8")
        logger.debug(f"> controller class: {controller_class}")
        c = CONTROLLERS[controller_class].load_from_archive(archive)
        c.infos = json.loads(archive.read("infos").decode("utf-8"))
        return c
