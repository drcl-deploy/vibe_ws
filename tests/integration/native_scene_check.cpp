// Exercise the native SDK's damping law using the simulator's MuJoCo library.
#include <mujoco/mujoco.h>

#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

using Model = std::unique_ptr<mjModel, decltype(&mj_deleteModel)>;
using Data = std::unique_ptr<mjData, decltype(&mj_deleteData)>;

void Check(bool condition, const std::string& message) {
  if (!condition) throw std::runtime_error(message);
}

Model Load(const char* path) {
  char error[2048] = {};
  Model model(mj_loadXML(path, nullptr, error, sizeof(error)), mj_deleteModel);
  Check(bool(model), std::string(path) + ": " + error);
  return model;
}

template <typename T>
void Equal(const T* a, const T* b, int count, const char* name) {
  Check(std::equal(a, a + count, b), std::string("robot changed: ") + name);
}

void RobotContract(const mjModel* a, const mjModel* b) {
  Check(a->nq == b->nq && a->nv == b->nv && a->nu == b->nu &&
        a->njnt == b->njnt && a->nbody == b->nbody && a->ngeom == b->ngeom,
        "robot dimensions changed");
#define SAME(field, count) Equal(a->field, b->field, count, #field)
  SAME(qpos0, a->nq);
  SAME(body_mass, a->nbody); SAME(body_inertia, 3*a->nbody);
  SAME(body_pos, 3*a->nbody); SAME(body_quat, 4*a->nbody);
  SAME(body_ipos, 3*a->nbody); SAME(body_iquat, 4*a->nbody);
  SAME(jnt_type, a->njnt); SAME(jnt_pos, 3*a->njnt);
  SAME(jnt_axis, 3*a->njnt); SAME(jnt_range, 2*a->njnt);
  SAME(jnt_actfrcrange, 2*a->njnt); SAME(jnt_stiffness, a->njnt);
  SAME(dof_damping, a->nv); SAME(dof_armature, a->nv);
  SAME(dof_frictionloss, a->nv); SAME(dof_solref, mjNREF*a->nv);
  SAME(dof_solimp, mjNIMP*a->nv);
  SAME(actuator_trnid, 2*a->nu); SAME(actuator_gear, 6*a->nu);
  SAME(actuator_gainprm, mjNGAIN*a->nu); SAME(actuator_biasprm, mjNBIAS*a->nu);
  SAME(actuator_dynprm, mjNDYN*a->nu); SAME(actuator_forcerange, 2*a->nu);
  SAME(actuator_ctrlrange, 2*a->nu);
  SAME(geom_type, a->ngeom); SAME(geom_size, 3*a->ngeom);
  SAME(geom_pos, 3*a->ngeom); SAME(geom_quat, 4*a->ngeom);
  SAME(geom_friction, 3*a->ngeom); SAME(geom_solref, mjNREF*a->ngeom);
  SAME(geom_solimp, mjNIMP*a->ngeom); SAME(geom_contype, a->ngeom);
  SAME(geom_conaffinity, a->ngeom); SAME(geom_condim, a->ngeom);
#undef SAME
}

void SceneContract(const mjModel* m) {
  Check(m->nu == 29, "expected G1 29 motors");
  mjOption original;
  mj_defaultOption(&original);
#define OPTION(field) Check(m->opt.field == original.field, "native option changed: " #field)
  OPTION(timestep); OPTION(integrator); OPTION(solver); OPTION(cone);
  OPTION(iterations); OPTION(ls_iterations); OPTION(jacobian);
  OPTION(tolerance); OPTION(ls_tolerance); OPTION(impratio);
  OPTION(disableflags); OPTION(enableflags); OPTION(noslip_iterations);
  OPTION(density); OPTION(viscosity);
#undef OPTION
  Equal(m->opt.gravity, original.gravity, 3, "gravity");
  const int cube = mj_name2id(m, mjOBJ_BODY, "cube");
  const int core = mj_name2id(m, mjOBJ_GEOM, "cube_core");
  const int floor = mj_name2id(m, mjOBJ_GEOM, "floor");
  const int camera = mj_name2id(m, mjOBJ_CAMERA, "head_cam");
  Check(cube >= 0 && core >= 0 && floor >= 0 && camera >= 0, "missing scene element");
  Check(m->body_mass[cube] == 0.62369, "cube mass");
  for (int i=0; i<3; ++i) {
    Check(m->body_inertia[3*cube+i] == 0.0386285, "native cube inertia");
    Check(m->geom_size[3*core+i] == 0.3048, "cube half extent");
    Check(m->geom_friction[3*core+i] == (i == 2 ? 0.0001 : 0.6), "cube friction");
    Check(m->geom_friction[3*floor+i] == (i == 0 ? 1.0 : i == 1 ? 0.005 : 0.0001),
          "floor friction");
  }
  Check(m->geom_type[floor] == mjGEOM_PLANE && m->nhfield == 0, "expected flat floor");
  Check(m->cam_fovy[camera] == 42.5, "camera FOV");
  for (int i=0; i<6; ++i) {
    int face = mj_name2id(m, mjOBJ_GEOM, ("cube_face_" + std::to_string(i)).c_str());
    Check(face >= 0 && !m->geom_contype[face] && !m->geom_conaffinity[face],
          "visual cube faces must not collide");
  }
}

void Damp(const mjModel* m, mjData* d) {
  // Same torque equation and sensor layout as RobotBridge::run with Y's kd=5.
  // Deterministic per-step refresh; this does not model DDS/thread scheduling.
  for (int i=0; i<m->nu; ++i) d->ctrl[i] = -5.0*d->sensordata[i+m->nu];
  mj_step(m, d);
}

void Settles(const mjModel* m, const mjModel* baseline) {
  Data d(mj_makeData(m), mj_deleteData);
  Data old(baseline ? mj_makeData(baseline) : nullptr, mj_deleteData);
  mj_forward(m, d.get());
  if (baseline) {
    Check(baseline->nq == m->nq && baseline->nv == m->nv &&
          baseline->opt.timestep == m->opt.timestep, "baseline dimensions/dt");
    mj_forward(baseline, old.get());
  }
  double sum=0, peak=0, difference=0;
  int count=0;
  for (int s=0; s<int(15/m->opt.timestep); ++s) {
    Damp(m, d.get());
    Check(std::abs(d->time-(s+1)*m->opt.timestep) < 1e-8, "simulation reset");
    if (baseline) {
      Damp(baseline, old.get());
      for (int i=0; i<m->nq; ++i)
        difference = std::max(difference, std::abs(d->qpos[i]-old->qpos[i]));
      for (int i=0; i<m->nv; ++i)
        difference = std::max(difference, std::abs(d->qvel[i]-old->qvel[i]));
    }
    for (int i=0; i<m->nu; ++i) {
      double v=d->qvel[m->jnt_dofadr[m->actuator_trnid[2*i]]];
      Check(std::isfinite(v), "nonfinite velocity");
      if (s*m->opt.timestep > 10) { sum+=v*v; ++count; peak=std::max(peak,std::abs(v)); }
    }
  }
  double rms=std::sqrt(sum/count);
  std::cout << "15 s Y-damping: final 5 s joint speed RMS=" << rms
            << ", peak=" << peak << " rad/s\n";
  // Baseline is ~0.015 RMS / 0.082 peak. Broken scene is >10 RMS / >40 peak.
  Check(rms < 0.05 && peak < 0.3, "damping did not settle");
  for (int i=0; i<mjNWARNING; ++i) Check(d->warning[i].number == 0, "MuJoCo warning");
  if (baseline) {
    std::cout << "Maximum qpos/qvel difference from Phase 0: " << difference << '\n';
    Check(difference < 1e-10, "native trajectory differs from Phase 0");
  }
}

int main(int argc, char** argv) {
  try {
    Check(argc == 4 || argc == 5, "usage: native_scene_check ROBOT COPY SCENE [PHASE0_SCENE]");
    std::cout << "MuJoCo " << mj_versionString() << '\n';
    auto robot=Load(argv[1]), copy=Load(argv[2]), scene=Load(argv[3]);
    RobotContract(robot.get(), copy.get());
    SceneContract(scene.get());
    Model baseline(argc == 5 ? Load(argv[4]) : Model(nullptr, mj_deleteModel));
    Settles(scene.get(), baseline.get());
    std::cout << "PASS native robot, contacts, timestep and damping\n";
  } catch (const std::exception& e) {
    std::cerr << "FAIL " << e.what() << '\n';
    return 1;
  }
}
