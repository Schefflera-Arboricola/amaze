""" Implements a wrapper around common models from stable baselines 3 """

import io
import json
from typing import Optional, Dict, Type, Union, Tuple
from zipfile import ZipFile

import numpy as np
import torch
from gymnasium import Space
from gymnasium.spaces import Discrete, Box
from stable_baselines3 import SAC, A2C, DQN, PPO, TD3
from stable_baselines3.common.base_class import BaseAlgorithm

from amaze.extensions.sb3.utils import IOMapper
from amaze.simu.controllers.base import BaseController
from amaze.simu.controllers.control import save
from amaze.simu.pos import Vec
from amaze.simu.types import InputType, OutputType, State

_classes = {
    c.__name__: c for c in [
        SAC, A2C, DQN, PPO, TD3
    ]
}
_i_types_mapping: Dict[int, InputType] = {
    1: InputType.DISCRETE,
    3: InputType.CONTINUOUS
}
_o_types_mapping: Dict[Type[Space], OutputType] = {
    Discrete: OutputType.DISCRETE,
    Box: OutputType.CONTINUOUS
}


def wrapped_sb3_model(model_type: Type[BaseAlgorithm]):
    """ Creates a class wrapping a specific stable baselines 3 model.

    Internal use only.
    """

    class SB3Controller(model_type, BaseController):
        simple = False

        _model_type = model_type

        def __init__(self, *_args, **_kwargs):
            # noinspection PyTypeChecker
            BaseController.__init__(self, None, None, None)

            # print(f"[kgd-debug] policy={self.policy.__class__.__name__}"
            #       f" {self._i_type=} {self._o_type=} {self._vision=}")

        def _setup_model(self) -> None:
            model_type._setup_model(self)
            print("[kgd-debug] SB3 model setup")
            BaseController.__init__(
                self,
                _i_types_mapping[len(self.observation_space.shape)],
                _o_types_mapping[self.action_space.__class__],
                (None if self._input_type is InputType.DISCRETE
                 else self.observation_space.shape[1])
            )

            self._mapper = IOMapper(observation_space=self.observation_space,
                                    action_space=self.action_space)

        @classmethod
        def __repr__(cls) -> str:
            return f"SB3.Controller[{cls._model_type.__name__}]"

        def __call__(self, inputs: State) -> Vec:
            return self._mapper.map_action(
                self.policy.predict(
                    self._mapper.map_observation(inputs),
                    deterministic=True)[0])

        def predict(
            self,
            observation: Union[np.ndarray, Dict[str, np.ndarray]],
            state: Optional[Tuple[np.ndarray, ...]] = None,
            episode_start: Optional[np.ndarray] = None,
            deterministic: bool = False,
        ) -> Tuple[np.ndarray, Optional[Tuple[np.ndarray, ...]]]:
            # print("predict", f"{deterministic=}")
            return super().predict(observation, state, episode_start,
                                   deterministic)

        def value(self, inputs: State) -> float:
            if isinstance(self._mapper.a_space, Discrete):
                actions = range(self._mapper.a_space.n)
            else:
                raise NotImplementedError
            obs, _ = self.policy.obs_to_tensor(
                self._mapper.map_observation(inputs))
            _, log_prob, _ = self.policy.evaluate_actions(
                obs, torch.Tensor(actions))

            return log_prob

        def reset(self):
            pass

        @staticmethod
        def inputs_types(): return list(InputType)

        @staticmethod
        def outputs_types(): return list(OutputType)

        def save(self, path: str, *_args, **_kwargs) -> None:
            # print("[kgd-debug] infos:\n", pprint.pformat(infos))
            save(self, path,
                 infos={
                     "algo": self._model_type.__name__,
                     "inputs": self._input_type.name,
                     "outputs": self._output_type.name,
                     "vision": self._vision,
                 },
                 *_args, **_kwargs)

        def save_to_archive(self, archive: ZipFile, *_args, **_kwargs) -> bool:
            """ Delegates savings of the internals to the SB3 model """
            buffer = io.BytesIO()
            self._model_type.save(self, buffer, *_args, **_kwargs)
            archive.writestr("sb3.zip", buffer.getvalue())
            return True

        @classmethod
        def load_from_archive(cls, archive: ZipFile, *_args, **_kwargs):
            """ Loads the SB3 specific contents from the archive """
            infos = json.loads(archive.read("infos"))
            # print("[kgd-debug] infos:\n", pprint.pformat(infos))
            buffer = io.BytesIO(archive.read("sb3.zip"))
            loaded_model = cls._model_type.load(buffer, *_args, **_kwargs)
            model = cls(policy=loaded_model.policy,
                        env=loaded_model.env,
                        device=loaded_model.device,
                        _init_setup_model=False)
            BaseController.__init__(
                model,
                input_type=InputType[infos["inputs"]],
                output_type=OutputType[infos["outputs"]],
                vision=infos["vision"],
            )
            model.__dict__.update(loaded_model.__dict__)
            if it := infos.get("inputs"):
                model._i_type = InputType[it]
            if ot := infos.get("outputs"):
                model._o_type = OutputType[ot]
            model._vision = infos.get("vision")
            return model

    return SB3Controller
