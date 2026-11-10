#!/usr/bin/env python3
"""network_test.py - валідація мережевих налаштувань та сервісів вбудованої системи Linux.

Що робить:
  1. Показує LISTEN-порти (ss -tuln) та ESTABLISHED-з'єднання.
  2. Читає ARP-кеш (ip neigh) і шлюз за замовчуванням (ip route).
  3. Пінгує шлюз і знайдені хости, перевіряє TCP-порти.
  4. Показує активні сесії (w) та процеси, що тримають порти (sudo ss -tulpn).
"""
import socket
import subprocess

# Критичні порти для перевірки: {порт: призначення}
CRITICAL_PORTS = {22: "SSH", 80: "HTTP", 8000: "API телеметрії", 1234: "TCP-потік SDR"}


def run_sys_command(cmd):
    """Виконує системну команду та повертає її stdout як текст."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=15)
        return result.stdout.strip()
    except FileNotFoundError:
        return f"[ПОМИЛКА] Команду '{cmd[0]}' не знайдено (встановіть відповідний пакет)."
    except Exception as e:
        return f"[ПОМИЛКА виконання команди] {e}"


def check_tcp_port(host, port, service_name="Сервіс"):
    """Швидка спроба TCP-з'єднання для перевірки відкритого порту."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                print(f"    -> [+] Порт {port} ({service_name}) ВІДКРИТИЙ.")
                return True
            print(f"    -> [-] Порт {port} ({service_name}) закритий.")
    except socket.error as e:
        print(f"    -> [!] Порт {port}: помилка сокета: {e}")
    return False


def ping(host):
    """ICMP-ping: 1 пакет, таймаут 1 с. Повертає True, якщо хост відповів."""
    try:
        res = subprocess.run(['ping', '-c', '1', '-W', '1', host],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0
    except FileNotFoundError:
        print("  [ПОМИЛКА] ping не знайдено: sudo apt install iputils-ping")
        return False


def parse_ss(output):
    """Парсить вивід ss у список словників (Python-змінні для аналізу)."""
    rows = []
    for line in output.splitlines()[1:]:  # пропускаємо заголовок
        p = line.split()
        if len(p) >= 5:
            rows.append({"netid": p[0], "state": p[1], "local": p[4],
                         "peer": p[5] if len(p) > 5 else ""})
    return rows


def show_local_network_state():
    print("\n=== 1. ЛОКАЛЬНІ ВІДКРИТІ ПОРТИ (LISTEN) ===")
    listen = parse_ss(run_sys_command(['ss', '-tuln']))
    if not listen:
        print("[ІНФО] Немає портів, що прослуховуються.")
    for r in listen:
        port = r["local"].rsplit(":", 1)[-1]
        name = CRITICAL_PORTS.get(int(port), "") if port.isdigit() else ""
        print(f"  {r['netid']:<4} {r['local']:<28} {('<- ' + name) if name else ''}")

    print("\n=== 2. ВСТАНОВЛЕНІ З'ЄДНАННЯ (ESTABLISHED) ===")
    est = parse_ss(run_sys_command(['ss', '-tun', 'state', 'established']))
    # з 'state established' колонка State відсутня, тому зсув інший - виводимо як є
    raw = run_sys_command(['ss', '-tun', 'state', 'established'])
    print(raw if len(raw.splitlines()) > 1 else "[ІНФО] Немає активних мережевих з'єднань.")


def get_gateway():
    """Шлюз за замовчуванням з 'ip route'."""
    out = run_sys_command(['ip', 'route', 'show', 'default'])
    parts = out.split()
    if 'via' in parts:
        return parts[parts.index('via') + 1]
    return None


def discover_and_test_hosts():
    print("\n=== 3. ШЛЮЗ ТА СУСІДНІ ХОСТИ (ARP-кеш) ===")
    gw = get_gateway()
    print(f"Шлюз за замовчуванням: {gw or 'не знайдено'}")

    hosts = {}
    for line in run_sys_command(['ip', '-4', 'neigh']).splitlines():
        p = line.split()
        if not p:
            continue
        state = p[-1]
        mac = p[p.index('lladdr') + 1] if 'lladdr' in p else "-"
        if state.upper() != "FAILED":
            hosts[p[0]] = (mac, state)
            print(f"  [ARP] Хост: {p[0]} | MAC: {mac} | Стан: {state}")
    if gw and gw not in hosts:
        hosts[gw] = ("-", "з таблиці маршрутів")
    if not hosts:
        print("[ІНФО] ARP-кеш порожній. Спершу виконайте ping шлюзу.")
        return

    print("\n=== 4. ПЕРЕВІРКА ХОСТІВ (PING & TCP) ===")
    for host in hosts:
        role = " (шлюз)" if host == gw else ""
        print(f"\nТестування {host}{role} ...")
        if ping(host):
            print("  [ОК] UP (відповідає на ping)")
            for port, name in CRITICAL_PORTS.items():
                check_tcp_port(host, port, name)
        else:
            print("  [ПОМИЛКА] DOWN або ICMP заблоковано firewall")


def show_active_users():
    print("\n=== 5. АКТИВНІ СЕСІЇ (хто зараз у системі) ===")
    out = run_sys_command(['w'])
    print(out if out else "[ІНФО] Не вдалося отримати список користувачів.")


def show_network_processes():
    print("\n=== 6. МЕРЕЖЕВІ ПРОЦЕСИ (хто слухає порти) ===")
    print("[!] Для PID потрібні права sudo (може запитати пароль).")
    out = run_sys_command(['sudo', 'ss', '-tulpn'])
    if out:
        for line in out.splitlines():
            if "users:" in line or "Netid" in line:
                print(line)
    else:
        print("[ІНФО] Немає даних або недостатньо прав.")


if __name__ == '__main__':
    print("Початок комплексного мережевого аудиту вбудованої системи...")
    show_local_network_state()
    discover_and_test_hosts()
    show_active_users()
    show_network_processes()
    print("\n=== Аудит завершено ===")
