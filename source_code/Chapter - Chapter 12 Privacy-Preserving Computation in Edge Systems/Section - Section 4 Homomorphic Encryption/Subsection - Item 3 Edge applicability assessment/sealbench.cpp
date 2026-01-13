#include 
#include 
#include 
#include 

int main() {
  using namespace seal;
  using clk = std::chrono::high_resolution_clock;

  // Parameter selection for edge: adjust poly_modulus_degree to fit slots and RAM
  EncryptionParameters parms(scheme_type::ckks);
  parms.set_poly_modulus_degree(16384); // change to 8192 if RAM constrained
  parms.set_coeff_modulus(CoeffModulus::Create(16384, {60,40,40,60}));

  auto context = SEALContext::Create(parms);
  KeyGenerator keygen(context);
  auto public_key = keygen.public_key();
  auto secret_key = keygen.secret_key();
  RelinKeys relin_keys = keygen.relin_keys_local();
  GaloisKeys gal_keys = keygen.galois_keys_local();

  CKKSEncoder encoder(context);
  Encryptor encryptor(context, public_key);
  Evaluator evaluator(context);
  Decryptor decryptor(context, secret_key);

  size_t slot_count = encoder.slot_count();
  std::vector input(slot_count, 0.0);
  for (size_t i = 0; i < 64; ++i) input[i] = 1.0; // example sensor channels

  double scale = pow(2.0, 40);
  Plaintext pt;
  encoder.encode(input, scale, pt);

  auto t0 = clk::now();
  Ciphertext ct;
  encryptor.encrypt(pt, ct);
  auto t1 = clk::now();

  // Simulate one linear layer: multiply by plaintext weights (packed similarly)
  std::vector weights(slot_count, 0.5);
  Plaintext pt_w; encoder.encode(weights, scale, pt_w);

  auto t2 = clk::now();
  evaluator.multiply_plain_inplace(ct, pt_w);
  evaluator.relinearize_inplace(ct, relin_keys);
  evaluator.rescale_to_next_inplace(ct);
  auto t3 = clk::now();

  // Optional rotations (simulate aggregation)
  evaluator.rotate_vector_inplace(ct, 1, gal_keys);
  auto t4 = clk::now();

  // Decrypt and decode to verify correctness
  Plaintext result_pt;
  decryptor.decrypt(ct, result_pt);
  std::vector result;
  encoder.decode(result_pt, result);

  auto t5 = clk::now();
  std::cout << "Encrypt(ms): " << std::chrono::duration(t1-t0).count()
            << " Compute(ms): " << std::chrono::duration(t4-t2).count()
            << " Decrypt(ms): " << std::chrono::duration(t5-t4).count() << std::endl;
  return 0;
}