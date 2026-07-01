param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    [Parameter(Mandatory=$true)]
    [string]$AppName,
    [string]$PgConnString = ""
)

Write-Host "Implementando Alt Pruebas en Azure App Service $AppName..." -ForegroundColor Green

# 1 --- Empaquetar codigo ---
$zipPath = "$env:TEMP\altpruebas.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path @(
    "app.py", "scrapers.py", "db_manager.py", "startup.sh",
    "templates\index.html", "static\css\styles.css",
    "requirements.txt"
) -DestinationPath $zipPath

# 2 --- Verificar / crear App Service ---
$existing = az webapp list --resource-group $ResourceGroup --query "[?name=='$AppName']" 2>$null
if (-not $existing -or $existing -eq '[]') {
    Write-Host "Creando App Service..." -ForegroundColor Yellow
    az group create --name $ResourceGroup --location eastus
    az appservice plan create --name "$AppName-plan" --resource-group $ResourceGroup --sku B1 --is-linux
    az webapp create --resource-group $ResourceGroup --plan "$AppName-plan" --name $AppName --runtime "PYTHON:3.14"
    az webapp config set --resource-group $ResourceGroup --name $AppName --startup-file "startup.sh"
    az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
}

# 3 --- Configurar conexion PostgreSQL ---
if ($PgConnString) {
    az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings "AZURE_POSTGRESQL_CONNECTIONSTRING=$PgConnString"
}

# 4 --- Desplegar zip ---
az webapp deploy --resource-group $ResourceGroup --name $AppName --src-path $zipPath --type zip --async true

Write-Host "Despliegue iniciado!" -ForegroundColor Green
Write-Host "  1. Ve a https://$AppName.azurewebsites.net" -ForegroundColor Cyan
Write-Host "  2. Revisa los logs en: Portal > App Service > Log stream" -ForegroundColor Cyan
Write-Host "  3. Para verificar la BD: az webapp ssh --resource-group $ResourceGroup --name $AppName" -ForegroundColor Cyan
