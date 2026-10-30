# Installing perf, iotop, and ltrace Tools

<!-- md-trans-meta sourceCommit=1a4bf651bbf53e6c2985f2817011402368a43db9 translatedAt=2026-10-10T12:15:29.836Z pushedAt=2026-10-15T10:59:32.281Z -->

> [!NOTE] Note
> perf, iotop, and ltrace are third-party tools. The following installation methods are examples only. Adapt them to your actual environment.

- On the Ubuntu 20.04 operating system, run the following command to install.
  - iotop tool installation method:

    ```sh
    apt-get install iotop
    ```

  - perf tool installation method:

    ```sh
    apt-get install linux-tools-common
    ```

  After the installation is complete, run the perf command, and then follow the system prompts to install linux-tools-x and linux-cloud-x using apt-get install.

  - ltrace tool installation method:

    ```sh
    apt-get install ltrace
    ```

- On the Ubuntu 18.04 operating system, run the following command to install.
  - iotop tool installation method:

    This section uses Python 3 as an example. If you use another Python version, adapt the steps accordingly.

    ```sh
    wget http://guichaz.free.fr/iotop/files/iotop-0.6.tar.bz2
    tar -xvf iotop-0.6.tar.bz2
    cd iotop-0.6
    sed -i 's/itervalues/values/g' setup.py
    python3 setup.py build
    python3 setup.py install
    ln -s /usr/local/python3/sbin/iotop /usr/sbin/iotop
    ln -s /usr/local/python3/bin/iotop /usr/bin/iotop
    ```

  - perf tool installation method:

    ```sh
    apt-get install linux-tools-common
    ```

    After the installation is complete, run the perf command and, following the system prompts, continue to use apt-get install to install linux-tools-x and linux-cloud-x.

  - ltrace tool installation method:

    ```sh
    apt-get install ltrace
    ```

- For CentOS 7.6, EulerOS, OpenEuler20.03, OpenEuler22.03, and KylinV10SP1 operating systems with the x86\_64 architecture, run the following command to install.

  ```sh
  yum install perf iotop ltrace
  ```

- For the KylinV10SP1 operating system with the ARM architecture, only the iotop tool needs to be installed. Run the following command to install.

  ```sh
  yum install iotop
  ```

> [!NOTE] Note
>
> - The preceding commands use the root user as an example. For a non-root user, add `sudo` before the command.
> - The iotop tool does not support use in containers.
> - After installing the perf, iotop, and ltrace tools, you need to [configure user permissions](config_user_permission.md).
