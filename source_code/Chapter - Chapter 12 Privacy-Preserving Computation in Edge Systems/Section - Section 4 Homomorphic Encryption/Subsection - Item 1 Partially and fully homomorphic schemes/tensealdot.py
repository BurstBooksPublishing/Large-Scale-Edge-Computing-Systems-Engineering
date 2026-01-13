import tenseal as ts
import numpy as np

# Client (edge device): create context and encrypt feature vector
poly_deg = 8192                          # ring dimension, affects security/latency
coeff_mod_bit_sizes = [60, 40, 40, 60]  # level configuration for depth
ctx = ts.context(ts.SCHEME_TYPE.CKKS, poly_deg, -1, coeff_mod_bit_sizes)
ctx.global_scale = 2**40                 # CKKS scaling factor
ctx.generate_galois_keys()              # enable vector rotations if needed

features = np.array([0.12, 0.34, 0.56, 0.78], dtype=float)
enc_features = ts.ckks_vector(ctx, features)  # encrypt and pack vector

# Serialize ciphertext to send to server
cipher_bytes = enc_features.serialize()      # small optimization: use network-friendly bytes

# Server: load context (public params) and perform encrypted dot product
server_ctx = ts.context_from(ctx.serialize())  # server holds public context (no secret key)
server_ctx.make_context_public()
enc_vec = ts.ckks_vector_from(server_ctx, cipher_bytes)

weights = np.array([1.5, -0.7, 0.25, 0.9], dtype=float)  # plaintext model weights
# Perform SIMD-packed dot product: elementwise multiply then sum (rotations optional)
enc_result = enc_vec.dot(weights.tolist())  # TenSEAL optimized routine

# Server returns the ciphertext bytes
result_bytes = enc_result.serialize()

# Client: decrypt result
dec_result = ts.ckks_vector_from(ctx, result_bytes)
print("Decrypted dot product:", dec_result.decrypt()[0])  # first slot contains dot product