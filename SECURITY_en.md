# Security Statement

## User Recommendations

For security reasons, do not use root or other administrator-type accounts to execute any commands. Follow the principle of minimum permissions.

## File Permission Control

- Set the running system umask value to 0027 or higher on the host (including the host machine) and in containers. This ensures that newly created folders have a default maximum permission of 750 and newly created files have a default maximum permission of 640.
- Implement permission control and other security measures for sensitive content such as personal privacy data, business assets, source files, and various files saved during Toolkit development. For example, permission control for this project's installation directory and input public data files. Refer to Appendix A: Recommended Maximum File (Folder) Permission Control for Various Scenarios at the end of this document.
- Implement permission control during installation and usage. Refer to Appendix A: Recommended Maximum File (Folder) Permission Control for Various Scenarios at the end of this document.

## Build Security Statement

When compiling and installing this project from source code, you need to compile it yourself. The compilation process generates some intermediate files. After compilation completes, implement permission control for intermediate files to ensure file security.

## Runtime Security Statement

- When Toolkit runs abnormally, it exits the process and prints error information. This is normal behavior. Locate the specific error cause based on the error prompt, including checking CANN logs and parsing generated Core Dump files.

## Public Network Address Statement

The public network addresses included in this project code are as follows:

| Type | Open Source Code Address | File Name | Public Network IP Address/URL/Domain/Email/Compressed File Address | Usage Description |
| :------------: |:------------------------------------------------------------------------------------------:|:----------------------------------------------------------| :---------------------------------------------------------- |:-----------------------------------------|
| Dependency | Not applicable | cann-cmake (makeself-fetch) | https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/makeself-release-2.5.0.tar.gz | Download makeself source code from OBS, used as build dependency |
| Dependency | Not applicable | cann-cmake (makeself-fetch) | https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/fix/makeself-2.5.0.patch | Download makeself patch from OBS, used as build dependency |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz | Download protobuf source code from gitcode, used as build dependency |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz | Download abseil source code from gitcode, used as build dependency |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1-h0/backport-CVE-2025-0838.patch | Download abseil security patch from gitcode (CVE-2025-0838 backport) |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz | Download boost source code from gitcode, used as build dependency |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/googletest/releases/download/v1.14.0/googletest-1.14.0.tar.gz | Download googletest source code from gitcode, used as build dependency |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h5/mockcpp-2.7-h5.patch | Download mockcpp patch from gitcode |
| Dependency | Not applicable | cann-cmake (add_cann_third_party) | https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz | Download mockcpp source code from gitcode, used as build dependency |
---

## Vulnerability Mechanism

[Vulnerability Management](https://gitcode.com/cann/community/blob/master/security/security.md)

## Appendix

### A: Recommended Maximum File (Folder) Permission Control for Various Scenarios

| Type | Linux Permission Reference Maximum Value |
| -------------- | ---------------  |
| User home directory | 750 (rwxr-x---) |
| Program files (including script files, library files, and so on) | 550 (r-xr-x---) |
| Program file directory | 550 (r-xr-x---) |
| Configuration file | 640 (rw-r-----) |
| Configuration file directory | 750 (rwxr-x---) |
| Log file (completed recording or archived) | 440 (r--r-----) |
| Log file (currently recording) | 640 (rw-r-----) |
| Log file directory | 750 (rwxr-x---) |
| Debug file | 640 (rw-r-----) |
| Debug file directory | 750 (rwxr-x---) |
| Temporary file directory | 750 (rwxr-x---) |
| Maintenance upgrade file directory | 770 (rwxrwx---) |
| Business data file | 640 (rw-r-----) |
| Business data file directory | 750 (rwxr-x---) |
| Key components, private keys, certificates, ciphertext file directory | 700 (rwx------) |
| Key components, private keys, certificates, encrypted ciphertext | 600 (rw-------) |
| Encryption and decryption interfaces, encryption and decryption scripts | 500 (r-x------) |
