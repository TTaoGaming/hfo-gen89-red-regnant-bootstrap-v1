<#
windows_service_install.ps1

Example: create a scheduled task that runs the orchestrator at startup and restarts on failure.
Requires: administrator privileges to register scheduled task.

Use NSSM (https://nssm.cc) for a true Windows service if desired.
#>

$python = "python"
$script = "c:\\hfoDev\\hfo_gen_89_hot_obsidian_forge\\0_bronze\\resources\\hfo_eval_orchestrator.py"
$model = "qwen2.5:7b"
$limit = 5

$action = "$python `"$script`" --model $model --limit $limit --interval 3600"

Write-Output "Creating scheduled task 'HFO Eval Orchestrator'..."

$taskName = "HFO Eval Orchestrator"
Register-ScheduledTask -TaskName $taskName -Trigger (New-ScheduledTaskTrigger -AtStartup) -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --model $model --limit $limit --interval 3600") -RunLevel Highest -Force

Write-Output "Scheduled task created. Use Task Scheduler to inspect or change triggers."

Write-Output "If you prefer NSSM, download NSSM and run:`n nssm install HFOEval $python `$script --model $model --limit $limit --interval 3600`n then configure restart options in the NSSM GUI."
