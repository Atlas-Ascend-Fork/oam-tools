# Environment Preparation

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T09:38:44.906Z pushedAt=2026-10-15T09:47:36.433Z -->

The Toolkit package has been installed in the CANN runtime environment. For details about the installation, see [*CANN Software Installation*](https://hiascend.com/document/redirect/CannCommunityInstSoftware).

After the CANN software is installed, when you use the CANN runtime user to compile and run, you need to log in to the environment as the CANN runtime user and run the **source \$_\{INSTALL\_DIR\}_/set\_env.sh** command to set the environment variables. *$\{INSTALL\_DIR\}* must be replaced with the storage path of the CANN software after installation. For example, if the software is installed by the root user, the default storage path after installation is /usr/local/Ascend/cann.

After the environment variables are set, you can directly enter the **asys** command to use the asys tool without entering the directory where the asys tool is located.
