#include 
#include 
#include 
#include 
#include 

// Simple thread-safe buffer for sensor messages
template
class MsgBuffer {
  std::deque> buf_;
  std::mutex mtx_;
public:
  void push(std::shared_ptr m){ std::lock_guard g(mtx_); buf_.push_back(m); }
  // pop earliest message with timestamp <= t_ms
  std::shared_ptr pop_until(int64_t t_ms){
    std::lock_guard g(mtx_);
    if(buf_.empty()) return nullptr;
    if(buf_.front()->header.stamp.sec*1000 + buf_.front()->header.stamp.nanosec/1000000 > t_ms) return nullptr;
    auto m = buf_.front(); buf_.pop_front(); return m;
  }
};

class FusionNode : public rclcpp::Node {
  rclcpp::Subscription::SharedPtr imu_sub_;
  rclcpp::Subscription::SharedPtr radar_sub_;
  MsgBuffer imu_buf_;
  MsgBuffer radar_buf_;
  Eigen::VectorXd x_; Eigen::MatrixXd P_;
public:
  FusionNode(): Node("fusion_node"), x_(6), P_(6,6){
    // init state and covariance
    x_.setZero(); P_.setIdentity();
    imu_sub_ = create_subscription(
      "/imu", 1000, [this](auto msg){ imu_buf_.push(std::make_shared(msg)); });
    radar_sub_ = create_subscription(
      "/radar", 100, [this](auto msg){ radar_buf_.push(std::make_shared(msg)); });
    // timer drives fusion loop at 50 Hz
    create_wall_timer(std::chrono::milliseconds(20), std::bind(&FusionNode::fusion_loop, this));
  }
private:
  void fusion_loop(){
    int64_t now_ms = this->now().seconds() * 1000 + this->now().nanoseconds() / 1000000;
    auto radar_msg = radar_buf_.pop_until(now_ms);
    if(!radar_msg) return;
    // align latest IMU up to radar timestamp
    int64_t radar_ts = radar_msg->header.stamp.sec*1000 + radar_msg->header.stamp.nanosec/1000000;
    while(true){
      auto imu_msg = imu_buf_.pop_until(radar_ts);
      if(!imu_msg) break;
      predict_with_imu(*imu_msg);
    }
    // measurement update for each radar detection (simple range-bearing -> position)
    for(const auto &obj : radar_msg->objects){
      Eigen::Vector2d z(obj.range * std::cos(obj.bearing), obj.range * std::sin(obj.bearing));
      ekf_update(z);
    }
    // publish fused state (omitted for brevity)
  }
  void predict_with_imu(const sensor_msgs::msg::Imu &imu){
    // small-angle kinematics prediction; implement efficient SIMD if needed
    double dt = 0.01; // use precise diff in production
    Eigen::MatrixXd F = Eigen::MatrixXd::Identity(6,6);
    // populate F and Q according to vehicle kinematics...
    Eigen::MatrixXd Q = 1e-3 * Eigen::MatrixXd::Identity(6,6);
    x_ = F * x_; P_ = F * P_ * F.transpose() + Q;
  }
  void ekf_update(const Eigen::Vector2d &z){
    Eigen::MatrixXd H(2,6); H.setZero();
    // map state to measurement (x,y)
    H(0,0) = 1; H(1,1) = 1;
    Eigen::MatrixXd R = 0.1 * Eigen::MatrixXd::Identity(2,2);
    Eigen::MatrixXd S = H*P_*H.transpose() + R;
    Eigen::MatrixXd K = P_ * H.transpose() * S.inverse();
    Eigen::VectorXd y(2); y << z(0) - x_(0), z(1) - x_(1);
    x_ = x_ + K*y; P_ = (Eigen::MatrixXd::Identity(6,6) - K*H) * P_;
  }
};

int main(int argc, char **argv){ rclcpp::init(argc, argv); rclcpp::spin(std::make_shared()); rclcpp::shutdown(); }