from typing import Any, Dict, Tuple

import numpy as np
import sapien
import torch
import math
from transforms3d.euler import euler2quat

from mani_skill.agents.multi_agent import MultiAgent
from mani_skill.agents.robots.panda import Panda
from mani_skill.envs.sapien_env import BaseEnv
from mani_skill.envs.utils.randomization.pose import random_quaternions
from mani_skill.sensors.camera import CameraConfig
from mani_skill.utils import common, sapien_utils
from mani_skill.utils.building import actors
from mani_skill.utils.registration import register_env
from mani_skill.utils.scene_builder.table import TableSceneBuilder
from mani_skill.utils.structs.pose import Pose
from mani_skill.utils.structs.types import GPUMemoryConfig, SimConfig


@register_env("TwoRobotPlate-v1", max_episode_steps=100)
class TwoRobotPlate(BaseEnv):
    """
    Task Description
    ----------------
    todo

    Randomizations
    --------------
    todo

    Success Conditions
    ------------------
    todo

    Visualization: TODO
    """

    SUPPORTED_ROBOTS = [("panda_wristcam", "panda_wristcam")]
    agent: MultiAgent[Tuple[Panda, Panda]]

    def __init__(
        self,
        *args,
        robot_uids=("panda_wristcam", "panda_wristcam"),
        robot_init_qpos_noise=0.02,
        **kwargs
    ):
        self.robot_init_qpos_noise = robot_init_qpos_noise
        super().__init__(*args, robot_uids=robot_uids, **kwargs)

    @property
    def _default_sim_config(self):
        return SimConfig(
            gpu_memory_config=GPUMemoryConfig(
                found_lost_pairs_capacity=2**25,
                max_rigid_patch_count=2**19,
                max_rigid_contact_count=2**21,
            )
        )

    @property
    def _default_sensor_configs(self):
        pose = sapien_utils.look_at(eye=[0.3, 0, 0.6], target=[-0.1, 0, 0.1])
        return [CameraConfig("base_camera", pose, 128, 128, np.pi / 2, 0.01, 100)]

    @property
    def _default_human_render_camera_configs(self):
        # pose = sapien_utils.look_at([1.4, 0.8, 0.75], [0.0, 0.1, 0.1]) # this perspective is good for demos
        pose = sapien_utils.look_at(eye=[0.6, 0.2, 0.4], target=[-0.1, 0, 0.1])
        return CameraConfig("render_camera", pose, 512, 512, 1, 0.01, 100)

    def _load_agent(self, options: dict):
        super()._load_agent(
            options, [sapien.Pose(p=[0, -1, 0]), sapien.Pose(p=[0, 1, 0])]
        )

    def _load_scene(self, options: dict):
        self.table_scene = TableSceneBuilder(
            env=self, robot_init_qpos_noise=self.robot_init_qpos_noise
        )
        self.table_scene.build()
        self.plate = actors.build_from_mesh(
            scene=self.scene,
            name="plate",
            initial_pose=sapien.Pose(p=[0, 0, 0.02]),
        )

    def _initialize_episode(self, env_idx: torch.Tensor, options: dict):
        with torch.device(self.device):
            b = len(env_idx)
            self.table_scene.initialize(env_idx)
            # the table scene initializes two robots. the first one self.agents[0] is on the left and the second one is on the right
            
            plate_xyz = torch.zeros((b, 3))
            plate_xyz[:, 0] = 0.2
            plate_xyz[:, 2] = 0.01
            theta = torch.tensor(math.radians(80))  # 例如，倾斜 30 度
        
            qx = torch.tensor(0)
            qy = torch.sin(theta / 2)
            qz = torch.tensor(0)
            qw = torch.cos(theta / 2)
            print(qx, qy, qz, qw)
            plate_quat = torch.zeros((b, 4))
            plate_quat[:, 0] = qx
            plate_quat[:, 1] = qy
            plate_quat[:, 2] = qz
            plate_quat[:, 3] = qw
            self.plate.set_pose(Pose.create_from_pq(p=plate_xyz, q=plate_quat))

            # torch.zeros((b, 3))
            # torch.rand((b, 2)) * 0.2 - 0.1
            # cubeA_xyz = torch.zeros((b, 3))
            # cubeA_xyz[:, 0] = torch.rand((b,)) * 0.1 - 0.05
            # cubeA_xyz[:, 1] = -0.15 - torch.rand((b,)) * 0.1 + 0.05
            # cubeB_xyz = torch.zeros((b, 3))
            # cubeB_xyz[:, 0] = torch.rand((b,)) * 0.1 - 0.05
            # cubeB_xyz[:, 1] = 0.15 + torch.rand((b,)) * 0.1 - 0.05
            # cubeA_xyz[:, 2] = 0.02
            # cubeB_xyz[:, 2] = 0.02

            # qs = random_quaternions(
            #     b,
            #     lock_x=True,
            #     lock_y=True,
            #     lock_z=False,
            # )
            # self.cubeA.set_pose(Pose.create_from_pq(p=cubeA_xyz, q=qs))

            # qs = random_quaternions(
            #     b,
            #     lock_x=True,
            #     lock_y=True,
            #     lock_z=False,
            # )
            # self.cubeB.set_pose(Pose.create_from_pq(p=cubeB_xyz, q=qs))

            # target_region_xyz = torch.zeros((b, 3))
            # target_region_xyz[:, 0] = torch.rand((b,)) * 0.1 - 0.05
            # target_region_xyz[:, 1] = -0.1
            # # set a little bit above 0 so the target is sitting on the table
            # target_region_xyz[..., 2] = 1e-3
            # self.goal_region.set_pose(
            #     Pose.create_from_pq(
            #         p=target_region_xyz,
            #         q=euler2quat(0, np.pi / 2, 0),
            #     )
            # )

    @property
    def left_agent(self) -> Panda:
        return self.agent.agents[0]

    @property
    def right_agent(self) -> Panda:
        return self.agent.agents[1]

    def evaluate(self):
        return {
            "is_cubeA_grasped": torch.tensor(0, dtype=torch.int),
            "is_cubeB_grasped": torch.tensor(0, dtype=torch.int),
            "is_cubeA_on_cubeB": torch.tensor(0, dtype=torch.int),
            "cubeB_placed": torch.tensor(0, dtype=torch.int),
            "success": torch.tensor(0, dtype=torch.uint8)  # uint8 is often used for booleans in PyTorch
        }
        pos_A = self.cubeA.pose.p
        pos_B = self.cubeB.pose.p
        offset = pos_A - pos_B
        xy_flag = (
            torch.linalg.norm(offset[..., :2], axis=1)
            <= torch.linalg.norm(self.cube_half_size[:2]) + 0.005
        )
        z_flag = torch.abs(offset[..., 2] - self.cube_half_size[..., 2] * 2) <= 0.005
        is_cubeA_on_cubeB = torch.logical_and(xy_flag, z_flag)
        cubeB_to_goal_dist = torch.linalg.norm(
            self.cubeB.pose.p[:, :2] - self.goal_region.pose.p[..., :2], axis=1
        )
        cubeB_placed = cubeB_to_goal_dist < self.goal_radius
        is_cubeA_grasped = self.left_agent.is_grasping(self.cubeA)
        is_cubeB_grasped = self.right_agent.is_grasping(self.cubeB)
        success = (
            is_cubeA_on_cubeB * cubeB_placed * (~is_cubeA_grasped) * (~is_cubeB_grasped)
        )
        return {
            "is_cubeA_grasped": is_cubeA_grasped,
            "is_cubeB_grasped": is_cubeB_grasped,
            "is_cubeA_on_cubeB": is_cubeA_on_cubeB,
            "cubeB_placed": cubeB_placed,
            "success": success.bool(),
        }

    def _get_obs_extra(self, info: Dict):
        obs = dict(
            left_arm_tcp=self.left_agent.tcp.pose.raw_pose,
            right_arm_tcp=self.right_agent.tcp.pose.raw_pose,
        )
        if "state" in self.obs_mode:
            print("state in obs mode")
        return obs

    def compute_dense_reward(self, obs: Any, action: torch.Tensor, info: Dict):
        return 10
        # Stage 1: Reach and grasp
        # reaching reward for both robots to their respective cubes
        cubeA_to_left_arm_tcp_dist = torch.linalg.norm(
            self.left_agent.tcp.pose.p - self.cubeA.pose.p, axis=1
        )
        right_arm_push_pose = Pose.create_from_pq(
            p=self.cubeB.pose.p
            + torch.tensor([0, self.cube_half_size[0] + 0.005, 0], device=self.device)
        )
        right_arm_to_push_pose_dist = torch.linalg.norm(
            right_arm_push_pose.p - self.right_agent.tcp.pose.p, axis=1
        )
        reach_reward = (
            1
            - torch.tanh(5 * cubeA_to_left_arm_tcp_dist)
            + 1
            - torch.tanh(5 * right_arm_to_push_pose_dist)
        ) / 2

        # grasp reward for left robot which needs to lift cubeA up eventually
        cubeA_pos = self.cubeA.pose.p
        cubeB_pos = self.cubeB.pose.p
        reward = (reach_reward + info["is_cubeA_grasped"]) / 2

        # pass condition for stage 1
        place_stage_reached = info["is_cubeA_grasped"]

        # Stage 2: Place bottom cube and still hold to cube A
        # place reward for bottom cube (cube B)
        cubeB_to_goal_dist = torch.linalg.norm(
            cubeB_pos[:, :2] - self.goal_region.pose.p[..., :2], axis=1
        )
        place_reward = 1 - torch.tanh(5 * cubeB_to_goal_dist)
        stage_2_reward = place_reward + info["is_cubeA_grasped"]
        reward[place_stage_reached] = 2 + stage_2_reward[place_stage_reached] / 2

        # pass condition for stage 2
        cubeB_placed_and_cubeA_grasped = info["cubeB_placed"] * info["is_cubeA_grasped"]

        # Stage 3: Place top cube while moving right arm away to give left arm space
        # place reward for top cube (cube A)
        goal_xyz = torch.hstack(
            [cubeB_pos[:, :2], (cubeB_pos[:, 2] + self.cube_half_size[2] * 2)[:, None]]
        )
        cubeA_to_goal_dist = torch.linalg.norm(goal_xyz - cubeA_pos, axis=1)
        place_reward = 1 - torch.tanh(5 * cubeA_to_goal_dist)

        # move right arm as close as possible to the y=0.2 line
        right_arm_leave_reward = 1 - torch.tanh(
            5 * (self.right_agent.tcp.pose.p[:, 1] - 0.2).abs()
        )
        stage_3_reward = place_reward * 2 + right_arm_leave_reward
        reward[cubeB_placed_and_cubeA_grasped] = (
            4 + stage_3_reward[cubeB_placed_and_cubeA_grasped]
        )
        # pass condition for stage 3
        cubes_placed = info["is_cubeA_on_cubeB"] * info["cubeB_placed"]
        # Stage 4: get both robots to stop grasping
        gripper_width = (self.left_agent.robot.get_qlimits()[0, -1, 1] * 2).to(
            self.device
        )  # NOTE: hard-coded with panda
        ungrasp_reward_left = (
            torch.sum(self.left_agent.robot.get_qpos()[:, -2:], axis=1) / gripper_width
        )
        ungrasp_reward_left[~info["is_cubeA_grasped"]] = 1.0
        ungrasp_reward_right = (
            torch.sum(self.right_agent.robot.get_qpos()[:, -2:], axis=1) / gripper_width
        )
        ungrasp_reward_right[~info["is_cubeB_grasped"]] = 1.0

        reward[cubes_placed] = (
            8 + (ungrasp_reward_left + ungrasp_reward_right)[cubes_placed] / 2
        )

        reward[info["success"]] = 10

        return reward

    def compute_normalized_dense_reward(
        self, obs: Any, action: torch.Tensor, info: Dict
    ):
        return self.compute_dense_reward(obs=obs, action=action, info=info) / 10
