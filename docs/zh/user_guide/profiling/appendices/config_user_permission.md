# 配置用户权限

完成[安装perf、iotop、ltrace工具](./install_perf_iotop_ltrace.md)后，需要给用户配置依赖权限。可参见如下步骤进行配置。

1. 以root用户登录环境。
2. 执行如下命令，将原环境perf的安全限制等级配置为0（即允许非root用户访问）。

   ```sh
   echo 0 > /proc/sys/kernel/perf_event_paranoid
   ```

   > [!NOTE]说明
   > 执行以上命令前请先执行`cat /proc/sys/kernel/perf_event_paranoid`，查看用户原本的值，以便后续恢复环境。

3. 执行如下命令，在/usr/bin/目录下创建文件msprof\_data\_collection.sh。

    ```sh
    cd /usr/bin
    touch msprof_data_collection.sh
    ```

4. 在msprof\_data\_collection.sh文件中添加脚本内容。
    1. 打开msprof\_data\_collection.sh文件。

        ```sh
        chmod u+wx msprof_data_collection.sh
        vi msprof_data_collection.sh
        ```

    2. 拷贝以下代码到msprof\_data\_collection.sh文件中。

        须先确保环境支持`pstree`命令。

        ```bash
        #!/bin/bash
        # This script is used to run perf/iotop/ltrace by profiling.

        command_type=$1
        command_param=$2
        script_dir="/usr/bin"
        script_name="$(basename "$0")"
        reg_int='^[1-9][0-9]{,6}$|^0$'

        function get_version(){
            if [ "${command_param}" = "perf" ] || [ "${command_param}" = "ltrace" ] || [ "${command_param}" = "iotop" ]; then
                "${command_param}" --version
            else
                printf "The value of the second parameter is incorrect, please enter the correct parameter, "
                printf "such as: perf, ltrace, iotop\n"
                exit 1
            fi
        }

        function kill_prof_cmd(){
            if [[ ${command_param} =~ ${reg_int} ]]; then
                ppid=`ps -o ppid= -p ${command_param}`
                ppid_user=$(ps -o uid -e -o pid | awk -va="${ppid}" '$2==a {print $1}')
                shell_user=`id -u ${SUDO_USER}`
                if [ "${ppid_user}" != "${shell_user}" ]; then
                    echo "UID of ${ppid} is:${ppid_user}, UID running this script is:${shell_user}"
                    exit 1
                fi
                pidLine=`pstree -T -p ${command_param}`
                pidLine=`echo $pidLine | awk 'BEGIN{ FS="(" ; RS=")" } NF>1 { print $NF }'`
                for pid in $pidLine
                    do
                        sudo kill -2 ${pid}
                    done
                exit 1
            else
                echo "Input pid:${command_param} error"
                exit 1
            fi
        }

        #当前跑这个脚本的用户和pid进程所属的用户要一致
        function check_pid(){
            if [[ ! ${command_param} =~ ${reg_int} ]]; then
                echo "Input pid:${command_param} error"
                exit 1
            fi
            params=$(cat /proc/sys/kernel/pid_max)
            if [[ ! "$params" =~ ${reg_int} ]]; then
                echo "Get max_pid error"
                exit 1
            fi
            if [ "${command_param}" -gt "${params}" ]; then
                echo "Input pid:${command_param} gt pid_max:${params}"
                exit 1
            fi
            pid_user=$(ps -o uid -e -o pid | awk -va="${command_param}" '$2==a {print $1}')
            shell_user=`id -u ${SUDO_USER}`
            if [ "${pid_user}" != "${shell_user}" ]; then
                echo "UID of ${command_param} is:${pid_user}, UID running this script is:${shell_user}"
                exit 1
            fi
        }

        function run_prof_trace_cmd(){
            check_pid
            perf trace -T --syscalls -p "${command_param}"
        }

        function run_ltrace_cmd(){
            check_pid
            ltrace -ttt -T -e pthread_attr_init -e pthread_create -e pthread_join -e pthread_mutex_init -p "${command_param}"
        }

        function run_iotop_cmd(){
            check_pid
            iotop -b -d 0.02 -P -t -p "${command_param}"
        }

        function check_username(){
            echo "${command_param}" | grep -q -E '^[ 0-9a-zA-Z./:]*$'
            result=$?
            if [ "$result" -ne 0 ]; then
                echo "Parameter:${command_param} is invalid!"
                exit 1
            fi
            if ! id -u "${command_param}" >/dev/null 2>&1 ; then
                echo "User:${command_param} does not exist"
                exit 1
            fi
        }

        function get_cmd(){
            params=$(cat /proc/sys/kernel/pid_max)
            if [[ ! "$params" =~ ${reg_int} ]]; then
                echo "Get max_pid error"
                exit 1
            fi
            digits=1
            while ((${params}>10)); do
                let "digits++"
                ((params /= 10))
            done
            compile='[1-9]'
            arr[0]='[0-9]'
            for((i=1;i<digits;i++)); do
                compile="${compile}[0-9]"
                arr[i]=${compile}
            done
            cmd="${script_dir}/${script_name} get-version perf,${script_dir}/${script_name} get-version ltrace,${script_dir}/${script_name} get-version iotop"
            for i in "${arr[@]}"; do
                cmd="${cmd},${script_dir}/${script_name} perf $i,${script_dir}/${script_name} kill $i,${script_dir}/${script_name} ltrace $i,${script_dir}/${script_name} iotop $i"
            done
            cmd="$command_param ALL=(ALL:ALL) NOPASSWD:${cmd}"
            cmd=$(echo -e "${cmd}\nDefaults env_reset")
            echo "${cmd}"
        }

        function set_sudoers(){
            if [ -d "/etc/sudoers.d" ]; then
                if [ -f "/etc/sudoers.d/${command_param}_profiling" ]; then
                    echo "The file /etc/sudoers.d/${command_param}_profiling already exist"
                fi
                echo "${cmd}" > /etc/sudoers.d/"${command_param}"_profiling
                result=$?
                if [ "$result" -ne 0 ]; then
                    echo "Set cmd to /etc/sudoers.d/${command_param}_profiling failed!"
                    exit 1
                else
                    echo "The user permission have been configured successfully. You can find the configuration file /etc/sudoers.d/${command_param}_profiling"
                    exit
                fi
            fi
            has_add=$(cat /etc/sudoers|grep "${script_name}"|grep "${command_param}")
            if [ "${has_add}" ]; then
                echo "The configure already exist, please confirm its content is correct"
                exit
            fi
            chmod u+w /etc/sudoers
            result=$?
            if [ "$result" -ne 0 ]; then
                echo "Permission configure failed"
                exit 1
            fi
            echo "${cmd}" >> /etc/sudoers
            chmod u-w /etc/sudoers
            echo "The user permission have been configured successfully. You can find the configuration file in the /etc/sudoers."
        }

        function handle_sudoers(){
            check_username
            get_cmd
            set_sudoers
        }

        function main(){
            if [ $# -ne 2 ]; then
                echo "The number of parameters is incorrect, please enter two parameters"
                exit 1
            fi
            if [ "${command_type}" = "set-sudoers" ]; then
                echo "Run set-sudoers cmd"
                handle_sudoers
            elif [ "${command_type}" = "get-version" ]; then
                #echo "Run get-version cmd"
                get_version
            elif [ "${command_type}" = "kill" ]; then
                #echo "kill cmd"
                kill_prof_cmd
            elif [ "${command_type}" = "perf" ]; then
                #echo "run perf trace cmd"
                run_prof_trace_cmd
            elif [ "${command_type}" = "ltrace" ] ; then
                #echo "run ltrace cmd"
                run_ltrace_cmd
            elif [ "${command_type}" = "iotop" ]; then
                #echo "run iotop cmd"
                run_iotop_cmd
            else
                printf "The value of the first parameter is incorrect, please enter the correct parameter, "
                printf "such as: set-sudoers, get-version, kill, perf, ltrace, iotop\n"
                exit 1
            fi
        }

        main "$@"
        ```

    3. 保存退出后，执行如下命令取消msprof\_data\_collection.sh文件的写权限：

        ```sh
        chmod u-w msprof_data_collection.sh
        ```

    4. 保证其他用户对msprof\_data\_collection.sh文件无写权限：

        ```sh
        chmod o-w msprof_data_collection.sh
        ```

5. 执行如下命令，给安装用户运行perf，iotop，ltrace工具添加权限（以HwHiAiUser为例）。

    ```sh
    /usr/bin/msprof_data_collection.sh set-sudoers HwHiAiUser
    ```

    执行完成后，返回如下所示表示执行成功。

    ```sh
    The user permission have been configured successfully.You can find the configuration file /etc/sudoers.d/HwHiAiuser_profiling
    ```

    > [!NOTE]说明
    >msprof\_data\_collection.sh会使用户获得sudo权限，存在提权风险，请谨慎使用，配置并完成采集操作后，请执行步骤6清除sudo权限。

6. 基于安全考虑，配置完以上权限并完成相应Profiling采集后，请进行配置清除操作。
    1. 检查是否存在“/etc/sudoers.d/\{安装用户名\}\_profiling”文件，若存在则删除该文件。
    2. 检查是否存在“/etc/sudoers”文件，若存在则：

        打开“/etc/sudoers”文件：

        ```sh
        chmod u+w /etc/sudoers
        vi /etc/sudoers
        ```

        删除文件内如下内容：

        ```sh
        huawei ALL=(ALL:ALL) NOPASSWD:/usr/bin/msprof_data_collection.sh get-version perf,/usr/bin/msprof_data_collection.sh get-version ltrace,/usr/bin/msprof_data_collection.sh get-version iotop,/usr/bin/msprof_data_collection.sh pkill perf,/usr/bin/msprof_data_collection.sh pkill ltrace,/usr/bin/msprof_data_collection.sh pkill iotop,/usr/bin/msprof_data_collection.sh perf [0-9],/usr/bin/msprof_data_collection.sh ltrace [0-9],/usr/bin/msprof_data_collection.sh iotop [0-9],/usr/bin/msprof_data_collection.sh perf [1-9][0-9],/usr/bin/msprof_data_collection.sh ltrace [1-9][0-9],/usr/bin/msprof_data_collection.sh iotop [1-9][0-9],/usr/bin/msprof_data_collection.sh perf [1-9][0-9][0-9],/usr/bin/msprof_data_collection.sh ltrace [1-9][0-9][0-9],/usr/bin/msprof_data_collection.sh iotop [1-9][0-9][0-9],/usr/bin/msprof_data_collection.sh perf [1-9][0-9][0-9][0-9],/usr/bin/msprof_data_collection.sh ltrace [1-9][0-9][0-9][0-9],/usr/bin/msprof_data_collection.sh iotop [1-9][0-9][0-9][0-9],/usr/bin/msprof_data_collection.sh perf [1-9][0-9][0-9][0-9][0-9],/usr/bin/msprof_data_collection.sh ltrace [1-9][0-9][0-9][0-9][0-9],/usr/bin/msprof_data_collection.sh iotop [1-9][0-9][0-9][0-9][0-9]
        Defaults env_reset
        ```

    3. 执行以下命令取消“/etc/sudoers”文件的写权限：

        ```sh
        chmod u-w /etc/sudoers
        ```

    4. 执行以下命令取消非root用户的访问权限，如下以原环境perf的安全限制等级取值4为例。

       ```sh
        echo 4 > /proc/sys/kernel/perf_event_paranoid
       ```
