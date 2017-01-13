#!/usr/bin/env python2.7
"""Helper script to generate a TrustKit or HPKP pin from a PEM/DER certificate file.
"""
from subprocess import Popen, PIPE
from sys import stdin
import os.path
import argparse
import hashlib
import base64


class SupportedKeyAlgorithmsEnum(object):
    RSA_2048 = 1
    RSA_4096 = 2
    ECDSA_SECP256R1 = 3


if __name__ == '__main__':
    # Parse the command line
    parser = argparse.ArgumentParser(description='Generate HPKP / TrustKit SSL Pins.')
    parser.add_argument('certificate', metavar='FILE', nargs='?', help='certificate file to read, if empty, stdin is used')
    parser.add_argument('--type', dest='type', action='store', default='PEM',
                        help='Certificate file type; "PEM" (default) or "DER".')
    args = parser.parse_args()

    if not args.certificate:
        certificate = stdin.read()
    elif os.path.isfile(args.certificate):
        with open(args.certificate, 'r') as certFile:
            certificate = certFile.read()
    else:
        raise ValueError('Could not open certificate file {}'.format(args.certificate))

    if args.type not in ['DER', 'PEM']:
        raise ValueError('Invalid certificate type {}; expected DER or PEM'.format(args.type))

    # Parse the certificate and print its information
    p1 = Popen('openssl x509 -inform {} -text -noout'.format(args.type), shell=True, stdin=PIPE, stdout=PIPE)
    certificate_txt = p1.communicate(input=certificate)[0]

    print '\nCERTIFICATE INFO\n----------------'
    p1 = Popen('openssl x509 -subject -issuer -fingerprint -sha1 -noout -inform {}'.format(
        args.type), shell=True, stdin=PIPE, stdout=PIPE)
    print p1.communicate(input=certificate)[0]

    # Extract the certificate key's algorithm
    # Tested on the output of OpenSSL 0.9.8zh and OpenSSL 1.0.2i
    alg_txt = certificate_txt.split('Public Key Algorithm:')[1].split('\n')[0].strip()
    key_algorithm = None
    if alg_txt == 'id-ecPublicKey':
        if 'prime256v1' in certificate_txt:
            key_algorithm = SupportedKeyAlgorithmsEnum.ECDSA_SECP256R1
    elif alg_txt == 'rsaEncryption':
        if 'Key: (2048 bit)' in certificate_txt:
            key_algorithm = SupportedKeyAlgorithmsEnum.RSA_2048
        elif 'Key: (4096 bit)' in certificate_txt:
            key_algorithm = SupportedKeyAlgorithmsEnum.RSA_4096

    if key_algorithm is None:
        raise ValueError('Error: Certificate key algorithm not supported: {}.'.format(alg_txt))


    # Generate the Subject Public Key Info hash
    if key_algorithm == SupportedKeyAlgorithmsEnum.ECDSA_SECP256R1:
        # The OpenSSL command is different for ECDSA
        openssl_alg = 'ec'
        trustkit_alg = 'kTSKAlgorithmEcDsaSecp256r1'
    elif key_algorithm == SupportedKeyAlgorithmsEnum.RSA_2048:
        openssl_alg = 'rsa'
        trustkit_alg = 'kTSKAlgorithmRsa2048'
    elif key_algorithm == SupportedKeyAlgorithmsEnum.RSA_4096:
        openssl_alg = 'rsa'
        trustkit_alg = 'kTSKAlgorithmRsa4096'
    else:
        raise ValueError('Unexpected key algorithm')

    p1 = Popen('openssl x509  -pubkey -noout -inform {} '
               '| openssl {} -outform DER -pubin -in /dev/stdin 2>/dev/null'.format(args.type,
                                                                                       openssl_alg),
            shell=True, stdin=PIPE, stdout=PIPE)
    spki = p1.communicate(input=certificate)[0]

    spki_hash = hashlib.sha256(spki).digest()
    hpkp_pin = base64.b64encode(spki_hash)

    print 'TRUSTKIT CONFIGURATION\n----------------------'
    print 'kTSKPublicKeyHashes: @[@"{}"] // You will also need to configure a backup pin'.format(hpkp_pin)
    print 'kTSKPublicKeyAlgorithms: @[{}]\n'.format(trustkit_alg)
    
