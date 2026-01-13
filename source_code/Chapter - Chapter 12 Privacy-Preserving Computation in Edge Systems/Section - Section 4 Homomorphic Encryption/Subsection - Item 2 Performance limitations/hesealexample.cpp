#include "seal/seal.h"
#include 
#include 
#include 

int main() {
  using namespace seal;
  EncryptionParameters parms(scheme_type::ckks);
  parms.set_poly_modulus_degree(8192); // N = 2^13
  parms.set_coeff_modulus(CoeffModulus::Create(8192, {60, 60, 60})); // ~180 bits

  auto ctx = SEALContext::Create(parms);
  KeyGenerator keygen(ctx);
  auto sk = keygen.secret_key();
  PublicKey pk; keygen.create_public_key(pk);
  RelinKeys relin_keys; keygen.create_relin_keys(relin_keys);

  CKKSEncoder encoder(ctx);
  Encryptor encryptor(ctx, pk);
  Evaluator evaluator(ctx);
  Decryptor decryptor(ctx, sk);

  std::vector input(encoder.slot_count(), 0.0);
  input[0] = 3.1415; input[1] = 2.718;
  double scale = pow(2.0, 40);

  Plaintext pt; encoder.encode(input, scale, pt);
  Ciphertext ct1, ct2;
  encryptor.encrypt(pt, ct1);
  encryptor.encrypt(pt, ct2);

  auto t0 = std::chrono::steady_clock::now();
  evaluator.multiply_inplace(ct1, ct2);             // homomorphic multiply
  evaluator.relinearize_inplace(ct1, relin_keys);   // key switching / relin
  evaluator.rescale_to_next_inplace(ct1);           // scale management
  auto t1 = std::chrono::steady_clock::now();

  std::chrono::duration dt = t1 - t0;
  std::cout << "Multiply+relin+rescale time (s): " << dt.count() << "\n";
  return 0;
}