on run
	set repoDir to POSIX path of ((path to me as text) & "Contents:Resources:ai-research-pipeline")
	set stopPath to repoDir & "/stop_ai_signal_center.command"
	set quotedStopPath to quoted form of stopPath
	try
		do shell script "if [ ! -x " & quotedStopPath & " ]; then exit 41; fi; /bin/zsh " & quotedStopPath & " >/dev/null 2>&1"
	on error errorMessage number errorNumber
		display alert "Unable to stop AI Signal Command Center" message ("Stop launcher failed with error " & errorNumber & ": " & errorMessage) as critical
	end try
end run