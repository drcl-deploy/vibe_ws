// Headless stand-in for unitree_mujoco on a machine with no display and without
// unitree_sdk2. Same bridge torque law, sensor layout and camera wire as
// simulate/src/{unitree_sdk2_bridge.h,head_camera_server.cc}. It is a substitute:
// the stock simulator did not run on this path.
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <arpa/inet.h>
#include <mujoco/mujoco.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joy.hpp>
#include <sstream>
#include <string>
#include <thread>
#include <unitree_hg/msg/low_cmd.hpp>
#include <unitree_hg/msg/low_state.hpp>
#include <vector>

#include "lodepng.h"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

namespace {

constexpr int kButtonRB = 5;

// Motor index = this order on the real robot and in the stock scene. A training
// model orders its actuators differently, so everything goes through these names.
const char* const kMotorJoints[29] = {
    "left_hip_pitch_joint",      "left_hip_roll_joint",      "left_hip_yaw_joint",
    "left_knee_joint",           "left_ankle_pitch_joint",   "left_ankle_roll_joint",
    "right_hip_pitch_joint",     "right_hip_roll_joint",     "right_hip_yaw_joint",
    "right_knee_joint",          "right_ankle_pitch_joint",  "right_ankle_roll_joint",
    "waist_yaw_joint",           "waist_roll_joint",         "waist_pitch_joint",
    "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint",
    "left_elbow_joint",          "left_wrist_roll_joint",    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint",
    "right_elbow_joint",         "right_wrist_roll_joint",   "right_wrist_pitch_joint",
    "right_wrist_yaw_joint"};

std::string leaf(const char* name) {
  const std::string s = name ? name : "";
  const auto slash = s.rfind('/');
  return slash == std::string::npos ? s : s.substr(slash + 1);
}

struct Args {
  std::string scene, log_dir, init_joints, init_base, init_object;
  std::string integrator = "scene";
  std::string actuator = "motor";
  int iterations = -1, ls_iterations = -1, port = 5555, fps = 50, textures = 1;
  int release_button = kButtonRB;  // RB: sling off at stand. A: sling off at clip start.
  int place_button = -1;  // Operator sets the ball down at this button, at the clip's offset from the robot.
  double impratio = -1.0, duration = 60.0;
  bool pin_until_stand = true;
  std::map<std::string, std::string> extra;
};

Args parse(int argc, char** argv) {
  Args a;
  for (int i = 1; i + 1 < argc; i += 2) {
    const std::string k = argv[i], v = argv[i + 1];
    if (k == "--scene") a.scene = v;
    else if (k == "--log-dir") a.log_dir = v;
    else if (k == "--init-joints") a.init_joints = v;
    else if (k == "--init-base") a.init_base = v;
    else if (k == "--init-object") a.init_object = v;
    else if (k == "--release-button") a.release_button = std::stoi(v);
    else if (k == "--place-button") a.place_button = std::stoi(v);
    else if (k == "--integrator") a.integrator = v;
    else if (k == "--actuator") a.actuator = v;
    else if (k == "--iterations") a.iterations = std::stoi(v);
    else if (k == "--ls-iterations") a.ls_iterations = std::stoi(v);
    else if (k == "--impratio") a.impratio = std::stod(v);
    else if (k == "--port") a.port = std::stoi(v);
    else if (k == "--fps") a.fps = std::stoi(v);
    else if (k == "--textures") a.textures = std::stoi(v);
    else if (k == "--duration") a.duration = std::stod(v);
    else if (k == "--pin-until-stand") a.pin_until_stand = std::stoi(v) != 0;
    else if (k != "--ros-args") throw std::runtime_error("unknown argument " + k);
  }
  if (a.scene.empty() || a.log_dir.empty())
    throw std::runtime_error("--scene and --log-dir are required");
  return a;
}

bool make_egl_context() {
  auto query = reinterpret_cast<PFNEGLQUERYDEVICESEXTPROC>(
      eglGetProcAddress("eglQueryDevicesEXT"));
  auto platform = reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
      eglGetProcAddress("eglGetPlatformDisplayEXT"));
  EGLDisplay dpy = EGL_NO_DISPLAY;
  EGLint major = 0, minor = 0;
  if (query && platform) {
    EGLDeviceEXT devices[8];
    EGLint count = 0;
    if (query(8, devices, &count))
      for (EGLint i = 0; i < count; ++i) {
        dpy = platform(EGL_PLATFORM_DEVICE_EXT, devices[i], nullptr);
        if (dpy != EGL_NO_DISPLAY && eglInitialize(dpy, &major, &minor)) break;
        dpy = EGL_NO_DISPLAY;
      }
  }
  if (dpy == EGL_NO_DISPLAY) {
    dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, &major, &minor)) return false;
  }
  const EGLint attribs[] = {EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
                            EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 24, EGL_STENCIL_SIZE, 8,
                            EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                            EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT, EGL_NONE};
  EGLConfig config;
  EGLint num = 0;
  if (!eglChooseConfig(dpy, attribs, &config, 1, &num) || num < 1) return false;
  if (!eglBindAPI(EGL_OPENGL_API)) return false;
  EGLContext ctx = eglCreateContext(dpy, config, EGL_NO_CONTEXT, nullptr);
  if (ctx == EGL_NO_CONTEXT) return false;
  return eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx);
}

class Host {
 public:
  Host(const Args& args, rclcpp::Node::SharedPtr node) : args_(args), node_(node) {
    char error[1000] = "";
    const bool binary = fs::path(args.scene).extension() == ".mjb";
    m_ = binary ? mj_loadModel(args.scene.c_str(), nullptr)
                : mj_loadXML(args.scene.c_str(), nullptr, error, sizeof(error));
    if (!m_) throw std::runtime_error("cannot load " + args.scene + ": " + error);
    d_ = mj_makeData(m_);
    if (args.integrator == "euler") m_->opt.integrator = mjINT_EULER;
    else if (args.integrator == "implicitfast") m_->opt.integrator = mjINT_IMPLICITFAST;
    else if (args.integrator == "implicit") m_->opt.integrator = mjINT_IMPLICIT;
    else if (args.integrator != "scene") throw std::runtime_error("unknown integrator");
    if (args.iterations > 0) m_->opt.iterations = args.iterations;
    if (args.ls_iterations > 0) m_->opt.ls_iterations = args.ls_iterations;
    if (args.impratio > 0) m_->opt.impratio = args.impratio;
    position_actuators_ = args.actuator == "position";
    if (m_->nu != 29) throw std::runtime_error("expected 29 actuators");
    for (int i = 0; i < m_->nu; ++i) {
      act_[i] = -1;
      for (int a = 0; a < m_->nu; ++a) {
        const int j = m_->actuator_trnid[2 * a];
        if (leaf(mj_id2name(m_, mjOBJ_JOINT, j)) != kMotorJoints[i]) continue;
        act_[i] = a;
        qadr_[i] = m_->jnt_qposadr[j];
        vadr_[i] = m_->jnt_dofadr[j];
      }
      if (act_[i] < 0) throw std::runtime_error(std::string("no actuator for ") + kMotorJoints[i]);
    }
    for (int j = 0; j < m_->njnt; ++j) {
      if (m_->jnt_type[j] != mjJNT_FREE) continue;
      const std::string body = leaf(mj_id2name(m_, mjOBJ_BODY, m_->jnt_bodyid[j]));
      if (body == "pelvis") {
        base_q_ = m_->jnt_qposadr[j];
        base_v_ = m_->jnt_dofadr[j];
      } else if (body == "object") {
        object_q_ = m_->jnt_qposadr[j];
        object_v_ = m_->jnt_dofadr[j];
      }
    }
    if (base_q_ < 0) throw std::runtime_error("no free joint on the pelvis");
    // Stock layout: jointpos | jointvel | jointactuatorfrc first. Absent on a
    // training-model scene; the same values are then read straight from state.
    stock_sensors_ = m_->nsensor >= 3 * m_->nu && m_->sensor_type[0] == mjSENS_JOINTPOS;
    imu_quat_ = sensor_adr("imu_quat");
    imu_gyro_ = sensor_adr("imu_gyro");
    imu_acc_ = sensor_adr("imu_acc");
    mj_resetData(m_, d_);
    if (!args.init_joints.empty()) {
      std::ifstream in(args.init_joints);
      for (int i = 0; i < m_->nu; ++i) {
        double q;
        if (!(in >> q)) throw std::runtime_error("--init-joints needs 29 values");
        d_->qpos[qadr_[i]] = q;
        d_->ctrl[act_[i]] = 0.0;
      }
    }
    if (!args.init_base.empty()) {
      std::ifstream in(args.init_base);
      for (int i = 0; i < 7; ++i)
        if (!(in >> d_->qpos[base_q_ + i])) throw std::runtime_error("--init-base needs 7 values");
    }
    if (!args.init_object.empty()) {
      if (object_q_ < 0) throw std::runtime_error("--init-object: scene has no object");
      std::ifstream in(args.init_object);
      for (int i = 0; i < 3; ++i)
        if (!(in >> d_->qpos[object_q_ + i])) throw std::runtime_error("--init-object needs 3 values");
    }
    mj_forward(m_, d_);
    std::copy(d_->qpos + base_q_, d_->qpos + base_q_ + 7, base_pose_);
    if (args.place_button >= 0) {
      if (object_q_ < 0) throw std::runtime_error("--place-button: scene has no object");
      const double yaw = yaw_of(base_pose_ + 3);
      const double dx = d_->qpos[object_q_] - base_pose_[0], dy = d_->qpos[object_q_ + 1] - base_pose_[1];
      object_offset_[0] = std::cos(yaw) * dx + std::sin(yaw) * dy;
      object_offset_[1] = -std::sin(yaw) * dx + std::cos(yaw) * dy;
      object_offset_[2] = d_->qpos[object_q_ + 2];
    }
    pinned_ = args.pin_until_stand;
    std::fill(std::begin(q_), std::end(q_), 0.f);
    std::fill(std::begin(dq_), std::end(dq_), 0.f);
    std::fill(std::begin(tau_), std::end(tau_), 0.f);
    std::fill(std::begin(kp_), std::end(kp_), 0.f);
    std::fill(std::begin(kd_), std::end(kd_), 0.f);

    state_pub_ = node_->create_publisher<unitree_hg::msg::LowState>("/lowstate", 10);
    cmd_sub_ = node_->create_subscription<unitree_hg::msg::LowCmd>(
        "/lowcmd", rclcpp::SensorDataQoS(),
        [this](unitree_hg::msg::LowCmd::SharedPtr msg) { on_cmd(*msg); });
    joy_sub_ = node_->create_subscription<sensor_msgs::msg::Joy>(
        "/joy", 10, [this](sensor_msgs::msg::Joy::SharedPtr msg) {
          if (static_cast<int>(msg->buttons.size()) > args_.release_button &&
              msg->buttons[args_.release_button] == 1 && pinned_.exchange(false))
            RCLCPP_INFO(node_->get_logger(), "base released at sim t=%.3f", d_->time);
          if (args_.place_button >= 0 && static_cast<int>(msg->buttons.size()) > args_.place_button &&
              msg->buttons[args_.place_button] == 1)
            place_pending_ = true;
        });
    row_ = 3 + m_->nq + m_->nv + 2 * m_->nu;
    log_.reserve(row_ * static_cast<size_t>(args.duration * 50 + 100));
    fs::create_directories(fs::path(args.log_dir) / "frames");
  }

  ~Host() {
    mj_deleteData(d_);
    mj_deleteModel(m_);
  }

  void start() {
    running_ = true;
    physics_ = std::thread(&Host::physics_loop, this);
    camera_ = std::thread(&Host::camera_loop, this);
    accept_ = std::thread(&Host::accept_loop, this);
  }

  void stop() {
    running_ = false;
    if (listen_fd_ >= 0) {
      ::shutdown(listen_fd_, SHUT_RDWR);
      ::close(listen_fd_);
    }
    physics_.join();
    camera_.join();
    accept_.join();
    write_logs();
  }

 private:
  static double yaw_of(const mjtNum* q) {
    return std::atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] * q[2] + q[3] * q[3]));
  }

  void place_object() {
    const mjtNum* base = d_->qpos + base_q_;
    const double yaw = yaw_of(base + 3);
    mjtNum* ball = d_->qpos + object_q_;
    ball[0] = base[0] + std::cos(yaw) * object_offset_[0] - std::sin(yaw) * object_offset_[1];
    ball[1] = base[1] + std::sin(yaw) * object_offset_[0] + std::cos(yaw) * object_offset_[1];
    ball[2] = object_offset_[2];
    std::fill(d_->qvel + object_v_, d_->qvel + object_v_ + 6, 0.0);
    RCLCPP_INFO(node_->get_logger(), "ball placed at %.3f %.3f, sim t=%.3f", ball[0], ball[1], d_->time);
  }

  int sensor_adr(const char* name) const {
    const int id = mj_name2id(m_, mjOBJ_SENSOR, name);
    return id < 0 ? -1 : m_->sensor_adr[id];
  }

  void on_cmd(const unitree_hg::msg::LowCmd& msg) {
    const double now = seconds();
    std::lock_guard<std::mutex> lock(cmd_mutex_);
    for (int i = 0; i < m_->nu; ++i) {
      const auto& c = msg.motor_cmd[i];
      q_[i] = c.q;
      dq_[i] = c.dq;
      tau_[i] = c.tau;
      kp_[i] = c.kp;
      kd_[i] = c.kd;
    }
    cmd_times_.push_back(now);
  }

  double seconds() const {
    return std::chrono::duration<double>(Clock::now() - t0_).count();
  }

  double joint_q(int i) const {
    return stock_sensors_ ? d_->sensordata[i] : d_->qpos[qadr_[i]];
  }
  double joint_v(int i) const {
    return stock_sensors_ ? d_->sensordata[i + m_->nu] : d_->qvel[vadr_[i]];
  }

  void apply_control() {
    std::lock_guard<std::mutex> lock(cmd_mutex_);
    for (int i = 0; i < m_->nu; ++i) {
      if (position_actuators_) {
        d_->ctrl[act_[i]] = q_[i];
        continue;
      }
      d_->ctrl[act_[i]] = tau_[i] + kp_[i] * (q_[i] - joint_q(i)) + kd_[i] * (dq_[i] - joint_v(i));
    }
  }

  void publish_state() {
    unitree_hg::msg::LowState msg;
    for (int i = 0; i < m_->nu; ++i) {
      auto& s = msg.motor_state[i];
      s.mode = 1;
      s.q = static_cast<float>(joint_q(i));
      s.dq = static_cast<float>(joint_v(i));
      s.tau_est = stock_sensors_ ? static_cast<float>(d_->sensordata[i + 2 * m_->nu])
                                 : static_cast<float>(d_->actuator_force[act_[i]]);
    }
    const mjtNum* q = imu_quat_ >= 0 ? d_->sensordata + imu_quat_ : d_->qpos + base_q_ + 3;
    const mjtNum* w = imu_gyro_ >= 0 ? d_->sensordata + imu_gyro_ : d_->qvel + base_v_ + 3;
    for (int i = 0; i < 4; ++i) msg.imu_state.quaternion[i] = static_cast<float>(q[i]);
    for (int i = 0; i < 3; ++i) {
      msg.imu_state.gyroscope[i] = static_cast<float>(w[i]);
      if (imu_acc_ >= 0)
        msg.imu_state.accelerometer[i] = static_cast<float>(d_->sensordata[imu_acc_ + i]);
    }
    msg.imu_state.rpy[0] = static_cast<float>(std::atan2(2 * (q[0] * q[1] + q[2] * q[3]),
                                                         1 - 2 * (q[1] * q[1] + q[2] * q[2])));
    msg.imu_state.rpy[1] = static_cast<float>(std::asin(std::clamp<double>(2 * (q[0] * q[2] - q[3] * q[1]), -1, 1)));
    msg.imu_state.rpy[2] = static_cast<float>(std::atan2(2 * (q[0] * q[3] + q[1] * q[2]),
                                                         1 - 2 * (q[2] * q[2] + q[3] * q[3])));
    msg.mode_machine = 5;
    msg.tick = static_cast<uint32_t>(std::lround(d_->time / 1e-3));
    state_pub_->publish(msg);
  }

  void log_row(double wall) {
    log_.push_back(d_->time);
    log_.push_back(wall);
    log_.push_back(pinned_.load() ? 1.0 : 0.0);
    log_.insert(log_.end(), d_->qpos, d_->qpos + m_->nq);
    log_.insert(log_.end(), d_->qvel, d_->qvel + m_->nv);
    for (int i = 0; i < m_->nu; ++i) log_.push_back(d_->actuator_force[act_[i]]);
    std::lock_guard<std::mutex> lock(cmd_mutex_);
    log_.insert(log_.end(), q_, q_ + m_->nu);
  }

  void physics_loop() {
    const double dt = m_->opt.timestep;
    const int log_every = static_cast<int>(std::lround(0.02 / dt));
    t0_ = Clock::now();
    t0_unix_ = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    long steps = 0;
    const auto start = Clock::now();
    while (running_ && rclcpp::ok()) {
      const auto a = Clock::now();
      {
        std::lock_guard<std::mutex> lock(sim_mutex_);
        apply_control();
        if (place_pending_.exchange(false)) place_object();
        mj_step(m_, d_);
        if (pinned_) {
          std::copy(base_pose_, base_pose_ + 7, d_->qpos + base_q_);
          std::fill(d_->qvel + base_v_, d_->qvel + base_v_ + 6, 0.0);
        }
        publish_state();
        if (steps % log_every == 0) log_row(seconds());
      }
      ++steps;
      const double cost = std::chrono::duration<double>(Clock::now() - a).count();
      step_max_ = std::max(step_max_, cost);
      step_sum_ += cost;
      const auto next = start + std::chrono::duration_cast<Clock::duration>(
                                    std::chrono::duration<double>(steps * dt));
      const auto now = Clock::now();
      if (now < next) std::this_thread::sleep_until(next);
      else if (now - next > std::chrono::milliseconds(1)) ++late_steps_;
      if (seconds() > args_.duration) running_ = false;
    }
    running_ = false;
    steps_ = steps;
    wall_ = std::chrono::duration<double>(Clock::now() - start).count();
    rclcpp::shutdown();
  }

  bool open_port() {
    listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd_ < 0) return false;
    int on = 1;
    ::setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(static_cast<uint16_t>(args_.port));
    if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) return false;
    return ::listen(listen_fd_, 4) == 0;
  }

  void accept_loop() {
    if (!open_port()) {
      std::fprintf(stderr, "camera port %d unavailable: %s\n", args_.port, std::strerror(errno));
      std::_Exit(3);
    }
    while (running_) {
      const int fd = ::accept(listen_fd_, nullptr, nullptr);
      if (fd < 0) continue;
      int on = 1;
      ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &on, sizeof(on));
      std::lock_guard<std::mutex> lock(clients_mutex_);
      clients_.push_back(fd);
    }
  }

  int find_camera() const {
    int id = mj_name2id(m_, mjOBJ_CAMERA, "head_cam");
    for (int i = 0; id < 0 && i < m_->ncam; ++i)
      if (std::string(mj_id2name(m_, mjOBJ_CAMERA, i)).find("head_cam") != std::string::npos) id = i;
    return id;
  }

  void camera_loop() {
    const int w = 112, h = 63;
    const int cam_id = find_camera();
    if (cam_id < 0 || !make_egl_context()) {
      std::fprintf(stderr, "no head_cam or EGL context failed (0x%x)\n", eglGetError());
      std::_Exit(4);
    }
    mjvScene scene;
    mjrContext context;
    mjvCamera camera;
    mjvOption option;
    mjv_defaultScene(&scene);
    mjv_makeScene(m_, &scene, 2000);
    mjr_defaultContext(&context);
    mjr_makeContext(m_, &context, mjFONTSCALE_100);
    mjr_resizeOffscreen(w, h, &context);
    scene.flags[mjRND_SHADOW] = 0;
    mjv_defaultCamera(&camera);
    camera.type = mjCAMERA_FIXED;
    camera.fixedcamid = cam_id;
    mjv_defaultOption(&option);
    option.flags[mjVIS_TEXTURE] = args_.textures != 0;
    std::fill(std::begin(option.geomgroup), std::end(option.geomgroup), 0);
    option.geomgroup[0] = option.geomgroup[2] = 1;
    const mjrRect viewport{0, 0, w, h};
    std::vector<unsigned char> up(w * h * 3), down(w * h * 3);
    const auto period = std::chrono::microseconds(1000000 / args_.fps);
    auto next = Clock::now();
    while (running_) {
      {
        std::lock_guard<std::mutex> lock(sim_mutex_);
        mjv_updateScene(m_, d_, &option, nullptr, &camera, mjCAT_ALL, &scene);
      }
      const double stamp = seconds();
      mjr_setBuffer(mjFB_OFFSCREEN, &context);
      mjr_render(viewport, &scene, &context);
      mjr_readPixels(up.data(), nullptr, viewport, &context);
      for (int r = 0; r < h; ++r)
        std::memcpy(down.data() + r * w * 3, up.data() + (h - 1 - r) * w * 3, w * 3);
      std::vector<unsigned char> png;
      if (lodepng::encode(png, down, w, h, LCT_RGB, 8) == 0) {
        broadcast(png);
        frames_.push_back(std::move(png));
        frame_times_.push_back(stamp);
      }
      next += period;
      const auto now = Clock::now();
      if (next < now) next = now;
      std::this_thread::sleep_until(next);
    }
    mjr_freeContext(&context);
    mjv_freeScene(&scene);
  }

  void broadcast(const std::vector<unsigned char>& png) {
    const uint32_t size = static_cast<uint32_t>(png.size());
    std::vector<unsigned char> record(4 + png.size());
    std::memcpy(record.data(), &size, 4);  // little endian, camera_wire.h FrameTcpRecord
    std::memcpy(record.data() + 4, png.data(), png.size());
    std::lock_guard<std::mutex> lock(clients_mutex_);
    for (auto it = clients_.begin(); it != clients_.end();) {
      size_t sent = 0;
      bool ok = true;
      while (sent < record.size()) {
        const ssize_t n = ::send(*it, record.data() + sent, record.size() - sent, MSG_NOSIGNAL);
        if (n <= 0) {
          ok = false;
          break;
        }
        sent += static_cast<size_t>(n);
      }
      if (ok) {
        ++it;
      } else {
        ::close(*it);
        it = clients_.erase(it);
      }
    }
  }

  void write_logs() {
    const fs::path dir(args_.log_dir);
    std::ofstream(dir / "log.bin", std::ios::binary)
        .write(reinterpret_cast<const char*>(log_.data()), log_.size() * sizeof(double));
    std::ofstream(dir / "cmd_times.bin", std::ios::binary)
        .write(reinterpret_cast<const char*>(cmd_times_.data()), cmd_times_.size() * sizeof(double));
    std::ofstream(dir / "frame_times.bin", std::ios::binary)
        .write(reinterpret_cast<const char*>(frame_times_.data()), frame_times_.size() * sizeof(double));
    for (size_t i = 0; i < frames_.size(); ++i) {
      char name[32];
      std::snprintf(name, sizeof(name), "%06zu.png", i);
      std::ofstream(dir / "frames" / name, std::ios::binary)
          .write(reinterpret_cast<const char*>(frames_[i].data()), frames_[i].size());
    }
    std::ostringstream meta;
    meta << "{\"nq\":" << m_->nq << ",\"nv\":" << m_->nv << ",\"nu\":" << m_->nu
         << ",\"row\":" << row_ << ",\"steps\":" << steps_ << ",\"wall_s\":" << wall_
         << ",\"step_mean_s\":" << (steps_ ? step_sum_ / steps_ : 0.0)
         << ",\"step_max_s\":" << step_max_ << ",\"late_steps\":" << late_steps_
         << ",\"t0_unix\":" << std::setprecision(17) << t0_unix_ << std::setprecision(6)
         << ",\"timestep\":" << m_->opt.timestep << ",\"integrator\":" << m_->opt.integrator
         << ",\"cone\":" << m_->opt.cone << ",\"iterations\":" << m_->opt.iterations
         << ",\"ls_iterations\":" << m_->opt.ls_iterations << ",\"impratio\":" << m_->opt.impratio
         << ",\"mujoco\":\"" << mj_versionString() << "\",\"actuator\":\"" << args_.actuator
         << "\",\"stock_sensors\":" << (stock_sensors_ ? "true" : "false")
         << ",\"scene\":\"" << args_.scene << "\"}\n";
    std::ofstream(dir / "log.json") << meta.str();
  }

  Args args_;
  rclcpp::Node::SharedPtr node_;
  mjModel* m_ = nullptr;
  mjData* d_ = nullptr;
  int act_[29], qadr_[29], vadr_[29];
  int base_q_ = -1, base_v_ = -1, object_q_ = -1, object_v_ = -1;
  double object_offset_[3] = {0.0, 0.0, 0.0};
  std::atomic<bool> place_pending_{false};
  bool stock_sensors_ = false, position_actuators_ = false;
  int imu_quat_ = -1, imu_gyro_ = -1, imu_acc_ = -1;
  mjtNum base_pose_[7];
  std::atomic<bool> pinned_{true}, running_{false};
  float q_[29], dq_[29], tau_[29], kp_[29], kd_[29];
  std::mutex cmd_mutex_, sim_mutex_, clients_mutex_;
  std::vector<double> log_, cmd_times_, frame_times_;
  std::vector<std::vector<unsigned char>> frames_;
  std::vector<int> clients_;
  size_t row_ = 0;
  int listen_fd_ = -1;
  long steps_ = 0, late_steps_ = 0;
  double step_max_ = 0.0, step_sum_ = 0.0, wall_ = 0.0, t0_unix_ = 0.0;
  Clock::time_point t0_ = Clock::now();
  std::thread physics_, camera_, accept_;
  rclcpp::Publisher<unitree_hg::msg::LowState>::SharedPtr state_pub_;
  rclcpp::Subscription<unitree_hg::msg::LowCmd>::SharedPtr cmd_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Joy>::SharedPtr joy_sub_;
};

}  // namespace

int main(int argc, char** argv) {
  const Args args = parse(argc, argv);
  rclcpp::init(0, nullptr);
  auto node = std::make_shared<rclcpp::Node>("bball_sim_host");
  Host host(args, node);
  host.start();
  rclcpp::spin(node);
  host.stop();
  return 0;
}
