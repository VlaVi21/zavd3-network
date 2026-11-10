#!/usr/bin/env bash
# collect_logs.sh - збирає виводи мережевих команд у logs/ та запускає аудит.
set -u
cd "$(dirname "$0")"
mkdir -p logs

GW=$(ip route | awk '/default/ {print $3; exit}')

ip a                      > logs/ip_a.txt
ifconfig                  > logs/ifconfig.txt 2>&1
ip route                  > logs/ip_route.txt
[ -n "$GW" ] && ping -c 2 -W 1 "$GW" > logs/ping_gateway.txt 2>&1
ip neigh                  > logs/ip_neigh.txt
ss -tuln                  > logs/ss_tuln.txt
sudo ss -tulpn            > logs/ss_tulpn.txt
w                         > logs/w.txt
python3 network_test.py   > logs/network_test_output.txt 2>&1

echo "Готово. Логи збережено в $(pwd)/logs/"
ls -1 logs/
