on run
	set repoDir to POSIX path of ((path to me as text) & "Contents:Resources:ai-research-pipeline")
	set launcherPath to repoDir & "/launch_ai_signal_center.command"
	set wrapperLogPath to repoDir & "/logs/app_wrapper_launch.log"
	set quotedLauncherPath to quoted form of launcherPath
	set quotedWrapperLogPath to quoted form of wrapperLogPath
	try
		do shell script "mkdir -p " & quoted form of (repoDir & "/logs") & "; if [ ! -x " & quotedLauncherPath & " ]; then exit 41; fi; nohup /bin/zsh " & quotedLauncherPath & " >> " & quotedWrapperLogPath & " 2>&1 &"
	on error errorMessage number errorNumber
		display alert "Unable to launch AI Signal Command Center" message ("Launcher failed with error " & errorNumber & ": " & errorMessage) as critical
	end try
end run