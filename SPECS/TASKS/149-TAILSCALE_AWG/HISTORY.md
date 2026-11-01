# HISTORY —149

## Предыдущая граница общего AWG-кода

Изначально codec/helpers/tests/testdata были извлечены из transport/wireguard
в transport/awgprofile, а WireGuard использовал делегирующие wrappers. Это
позволяло разделить codec с Tailscale, но создавало лишний package и большой
перенос исходных файлов. Прямой protocol/tailscale → transport/wireguard не
создаёт обратного импорта. По запросу ревью исходные пути восстанавливаются,
а typed Tailscale-profile API остаётся новым изолированным файлом WireGuard.

Изменение границы не переносит реализацию на1.15 и не снимает автоматически
текущие Tailscale/gVisor requirements. Проверка testing фиксируется отдельно
в PORTING_1_15.md на конкретных upstream revisions.
