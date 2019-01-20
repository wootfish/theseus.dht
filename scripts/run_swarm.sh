#!/bin/bash


N=${1:-10}


rm -rf /tmp/theseus_ports
rm -rf /tmp/theseus_logs
rm -rf /tmp/theseus_pids
mkdir /tmp/theseus_ports
mkdir /tmp/theseus_logs
mkdir /tmp/theseus_pids


for i in $( seq 1 $N ); do
    echo -n "$i  "
    PYTHONPATH=$(pwd)/swarm_plugins/ twistd -y ../main.tac --logfile=/tmp/theseus_logs/$i.log --pidfile=/tmp/theseus_pids/$i.pid
done


echo
read
killall twistd
