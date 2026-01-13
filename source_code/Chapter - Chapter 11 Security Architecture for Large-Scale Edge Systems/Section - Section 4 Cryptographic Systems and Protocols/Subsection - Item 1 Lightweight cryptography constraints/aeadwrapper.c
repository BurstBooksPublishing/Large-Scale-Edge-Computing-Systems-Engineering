/* Compile with -DUSE_HW_AES if platform HAL provides AES-CCM driver.
   Link mbedtls for CCM, and ascon_ref for fallback. */
#include 
#include 
#ifdef USE_HW_AES
#include "hal_crypto.h"    /* platform AES-CCM driver: hal_ccm_encrypt() */
#else
#include "mbedtls/ccm.h"   /* software CCM if desired */
#endif
#include "ascon.h"          /* Ascon AEAD reference API */

#define KEY_LEN 16          /* 128-bit keys */
#define TAG_LEN 16

/* Encrypt AEAD: key, nonce_len (12 typical), assoc, plaintext */
int aead_encrypt(const uint8_t key[KEY_LEN],
                 const uint8_t *nonce, size_t nonce_len,
                 const uint8_t *assoc, size_t assoc_len,
                 const uint8_t *pt, size_t pt_len,
                 uint8_t *ct, uint8_t tag[TAG_LEN])
{
#ifdef USE_HW_AES
    /* Hardware AES-CCM driver returns 0 on success */
    return hal_ccm_encrypt(key, KEY_LEN, nonce, nonce_len,
                           assoc, assoc_len, pt, pt_len, ct, tag, TAG_LEN);
#else
    /* Try mbed TLS CCM if available; otherwise use Ascon fallback */
#ifdef MBEDTLS_CCM_C
    mbedtls_ccm_context ctx;
    mbedtls_ccm_init(&ctx);
    if (mbedtls_ccm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, key, KEY_LEN * 8) != 0) {
        mbedtls_ccm_free(&ctx);
        return -1;
    }
    int ret = mbedtls_ccm_encrypt_and_tag(&ctx, pt_len, nonce, nonce_len,
                                          assoc, assoc_len, pt, ct, tag, TAG_LEN);
    mbedtls_ccm_free(&ctx);
    return ret;
#else
    /* Ascon-128a: ascon_aead_encrypt returns 0 on success */
    return ascon_aead_encrypt(tag, ct, key, nonce, nonce_len, assoc, assoc_len,
                              pt, pt_len);
#endif
#endif
}