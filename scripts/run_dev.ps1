# Run from project root dir

# Check if Docker engine is running
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker engine is not running. Starting Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    # Wait for Docker to be ready
    Write-Host "Waiting for Docker to start..."
    do {
        Start-Sleep -Seconds 2
        docker info 2>&1 | Out-Null
    } while ($LASTEXITCODE -ne 0)
}
Write-Host "Docker is ready."
docker compose -f ./compose.dev.yaml up --build
