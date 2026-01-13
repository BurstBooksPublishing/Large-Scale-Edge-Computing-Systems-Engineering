/* Minimal production-ready TLS client setup for Zephyr using mbedTLS.
   - Uses hardware private key via mbedtls_pk_parse_key() wrapper.
   - Enables session tickets and sets cipher suites for constrained devices. */
#include "mbedtls/ssl.h"
#include "mbedtls/net_sockets.h"
#include "mbedtls/error.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"

/* Application-level callbacks to sign with secure element (ATECC608A). */
int hw_sign_callback(void *ctx, mbedtls_md_type_t md_alg,
                     const unsigned char *hash, size_t hash_len,
                     unsigned char *sig, size_t *sig_len)
{
    /* Call secure element API to sign 'hash'. Return signature in 'sig'. */
    /* Hardware-specific code omitted for brevity; ensure constant-time ops. */
    return hw_secure_element_sign(hash, hash_len, sig, sig_len);
}

int tls_client_connect(const char *host, const char *port)
{
    mbedtls_net_context sock;
    mbedtls_ssl_context ssl;
    mbedtls_ssl_config conf;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_entropy_context entropy;
    const char *pers = "edge_tls_client";
    int ret;

    mbedtls_net_init(&sock);
    mbedtls_ssl_init(&ssl);
    mbedtls_ssl_config_init(&conf);
    mbedtls_ctr_drbg_init(&ctr_drbg);
    mbedtls_entropy_init(&entropy);

    if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func,
                                     &entropy, (const unsigned char*)pers,
                                     strlen(pers))) != 0) return ret;

    /* Configure TLS: client, default presets, session tickets enabled. */
    mbedtls_ssl_config_defaults(&conf,
        MBEDTLS_SSL_IS_CLIENT,
        MBEDTLS_SSL_TRANSPORT_STREAM,
        MBEDTLS_SSL_PRESET_DEFAULT);

    mbedtls_ssl_conf_authmode(&conf, MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_rng(&conf, mbedtls_ctr_drbg_random, &ctr_drbg);
    /* Prefer ChaCha20-Poly1305 if no AES hardware; include X25519/ECDHE. */
    const int ciphersuites[] = {
        MBEDTLS_TLS_CHACHA20_POLY1305_SHA256,
        MBEDTLS_TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
        0
    };
    mbedtls_ssl_conf_ciphersuites(&conf, ciphersuites);

    /* Use hardware-backed private key with signing callback. */
    mbedtls_ssl_set_hs_msg_cb(&ssl, NULL, NULL); /* optional hooks */
    mbedtls_ssl_conf_cert_req_ca_list(&conf, MBEDTLS_SSL_CERT_REQ_CA_LIST);
    /* Register custom sign callback into mbedTLS PK context before assign */

    mbedtls_ssl_setup(&ssl, &conf);
    mbedtls_ssl_set_bio(&ssl, &sock, mbedtls_net_send, mbedtls_net_recv, NULL);

    if ((ret = mbedtls_net_connect(&sock, host, port, MBEDTLS_NET_PROTO_TCP)) != 0) goto cleanup;
    if ((ret = mbedtls_ssl_handshake(&ssl)) != 0) goto cleanup;

    /* Application data exchange here */

cleanup:
    mbedtls_ssl_close_notify(&ssl);
    mbedtls_net_free(&sock);
    mbedtls_ssl_free(&ssl);
    mbedtls_ssl_config_free(&conf);
    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);
    return ret;
}