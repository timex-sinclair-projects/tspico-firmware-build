romupdate.tap: romupdate.bas romupdate_code.tap
	zmakebas -n romupdate -a 1 -o - romupdate.bas | cat - romupdate_code.tap > romupdate.tap

dckupdate.tap: dckupdate.bas dckupdate_code.tap
	zmakebas -n dckupdate -a 1 -o - dckupdate.bas | cat - dckupdate_code.tap > dckupdate.tap

nofile.tap: nofile_help.tap tc.tap
	cat nofile_help.tap tc.tap > nofile.tap

nofile_help.tap: nofile_help.bas
	zmakebas -n "No file!" -a 1 -o nofile_help.tap nofile_help.bas

tc.tap: tc.bas
	zmakebas -n tc -a 1 -o tc.tap tc.bas

