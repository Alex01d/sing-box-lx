# Embedded Tailscale AWG — Linux engineering

Статус фичи — [FEATURE 019](../SPECS/FEATURES/019-TAILSCALE_AWG/FEATURE.md).
Нужны совместимый peer/router и core с with_gvisor + with_tailscale + with_awg +
with_tailscale_awg. Headscale управляет identity/ACL/routes, а профиль AWG
распространяется оператором отдельно. Системный tailscaled не требуется.

```json
{
  "type": "tailscale",
  "tag": "private-net",
  "control_url": "https://headscale.example.invalid",
  "accept_routes": true,
  "awg": {
    "version": 2,
    "profile_id": "example",
    "parameters": {"s1": 64, "s2": 64, "s3": 32, "s4": 16,
      "h1": "100000-199999", "h2": "200000-299999",
      "h3": "300000-399999", "h4": "400000-499999"}
  }
}
```

Это synthetic example, не профиль production router. Auth key необязателен;
login URL/ручное одобрение используются штатно. Shared parameters должны
совпадать с совместимым peer. Profile не принимает WG private/public keys,
AllowedIPs или control commands. Неверный/необфусцирующий профиль отвергается
до запуска; никакого auto downgrade до WireGuard нет.

## Параллельный VLESS и внешний carrier

Разные правила могут направлять private назначения в Tailscale-AWG, а public —
в VLESS. Для вложенной цепочки у Tailscale endpoint задаётся detour с tag уже
существующего внешнего outbound:

```json
{"detour": "outer-vless", "underlay_mode": "auto"}
```

auto использует peer UDP через proxy с multi-destination UDP semantics
(например, VLESS XUDP/packetaddr); DERP/control TCP также идут через detour.
Для TCP-only proxy используйте underlay_mode=derp: peer UDP выключен, AWG
пакеты идут внутри DERP HTTPS/TCP. При отказе detour native fallback отсутствует.
Direct в peer status означает «без DERP», а не отсутствие внешнего proxy.
Маршрут outer-vless не должен зависеть от этого endpoint; dependency cycle
отвергается. Обычный WG без awg сохраняет прежнюю семантику, если не задан
новый underlay_mode; для его полного carrier задайте auto/derp явно.

## Launcher

Добавить Tailscale, выбрать WireGuard/AWG2/AWG3, импортировать native profile
JSON или отредактировать parameters. Export переносит profile, не identity.
Protected Tailscale networks preset привязывает CIDR/private suffixes к
конкретному endpoint; один элемент на строку. Он сохраняется без login/live
network map и блокирует применение при отсутствии target. Тег capability
проверяется до удаления узлов/полей. Backup новой функции использует marker 3;
старые приложения должны отвергать его целиком.

Configured/applied status не доказывает доступность peer. Проверять реальный
TCP/UDP и существующий StartConnectionTest; HTTP 403 является ответом приложения.
Peer relay и встроенный SSH server с AWG в engineering пока явно запрещены.
Linux manual acceptance, Android и остальные платформы ещё не завершены;
публикация immutable dependency pin/release — отдельный gate.
