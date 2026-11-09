[CmdletBinding()]
param(
    [string]$OutputPath,
    [string]$Connection = 'unspecified',
    [string]$Firmware = 'unknown',
    [string]$GogglesMode = 'unknown'
)

$ErrorActionPreference = 'Stop'
$allDevices = @(Get-PnpDevice -PresentOnly)
$candidates = @($allDevices | Where-Object {
    $_.InstanceId -match '^USB\\VID_(2CA3|18D1)' -or
    $_.FriendlyName -match 'DJI|Goggles|Android.*Accessory'
})
$propertyNames = @(
    'DEVPKEY_Device_HardwareIds',
    'DEVPKEY_Device_CompatibleIds',
    'DEVPKEY_Device_Service',
    'DEVPKEY_Device_DriverInfPath',
    'DEVPKEY_Device_DriverVersion',
    'DEVPKEY_Device_Manufacturer',
    'DEVPKEY_Device_BusReportedDeviceDesc',
    'DEVPKEY_Device_LocationPaths',
    'DEVPKEY_Device_Parent',
    'DEVPKEY_Device_ProblemCode'
)

$deviceRecords = @($candidates | ForEach-Object {
    $device = $_
    $properties = [ordered]@{}
    foreach ($propertyName in $propertyNames) {
        $property = Get-PnpDeviceProperty -InstanceId $device.InstanceId `
            -KeyName $propertyName -ErrorAction SilentlyContinue
        $properties[$propertyName] = if ($null -ne $property) { $property.Data } else { $null }
    }
    [ordered]@{
        status = [string]$device.Status
        class = $device.Class
        name = $device.FriendlyName
        instance_id = $device.InstanceId
        properties = $properties
    }
})

$os = Get-CimInstance Win32_OperatingSystem
$report = [ordered]@{
    schema_version = 1
    captured_utc = [DateTime]::UtcNow.ToString('o')
    connection = $Connection
    firmware_reported = $Firmware
    goggles_mode_reported = $GogglesMode
    os = [ordered]@{ name = $os.Caption; version = $os.Version; architecture = $os.OSArchitecture }
    gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion)
    candidate_devices = $deviceRecords
    usb_devices = @($allDevices | Where-Object { $_.InstanceId -like 'USB\*' } |
        Select-Object Status, Class, FriendlyName, InstanceId)
    limitations = @(
        'PnP inventory does not read USB endpoint descriptors or establish video-input support'
        'Candidate IDs include DJI and Google devices and do not authenticate a goggles model'
        'Missing properties are null; firmware and mode are operator reports'
        'Raw instance IDs can contain serial numbers; keep this report out of Git'
    )
}

$json = $report | ConvertTo-Json -Depth 8
if ($OutputPath) {
    $fullOutputPath = [IO.Path]::GetFullPath($OutputPath)
    if (Test-Path -LiteralPath $fullOutputPath) { throw "Output already exists: $fullOutputPath" }
    $parent = Split-Path -Parent $fullOutputPath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw "Missing output directory: $parent" }
    [IO.File]::WriteAllText($fullOutputPath, $json, [Text.UTF8Encoding]::new($false))
    Write-Output "Saved $($deviceRecords.Count) candidate device(s) to $fullOutputPath"
} else {
    Write-Output $json
}
