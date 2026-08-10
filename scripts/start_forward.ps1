# FALLBACK ONLY — the port-forward normally runs as a WorkstationOps instance
# (see WorkstationOps repo); use this only if that op is unavailable.
# Starts the userspace forward: Windows 0.0.0.0:4080 -> WSL:4080.
# The WSL IP changes across reboots, so it is derived at start time.
$wslIp = (wsl -d Ubuntu -- hostname -I).Trim().Split(' ')[0]
if (-not $wslIp) { Write-Error "could not determine WSL IP"; exit 1 }
Start-Process -WindowStyle Hidden -FilePath "python" `
    -ArgumentList "C:\Users\rtasseff\tcp_forward.py --listen-port 4080 --target-host $wslIp --target-port 4080"
Write-Host "Forwarding 0.0.0.0:4080 -> ${wslIp}:4080"
