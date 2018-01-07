python-2.7.3.msi
setx PATH "%PATH%;C:\Python27;C:\Python27\Lib;C:\Python27\Lib\site-packages;C:\Python27\Scripts;C:\jython2.5.2;%AUTOMATED_HOME%" /M
wxPython2.8-win32-unicode-2.8.12.1-py27
java -jar jython_installer-2.5.2.jar
robotframework-2.7.6.win32
robotframework-ride-1.1.win32
mkdir %UserProfile%\AppData\Roaming\RobotFramework\ride
copy settings.cfg %UserProfile%\AppData\Roaming\RobotFramework\ride /Y
copy TestRunnerAgent.py C:\Python27\Lib\site-packages\robotide\contrib\testrunner /Y
copy testrunnerplugin.py C:\Python27\Lib\site-packages\robotide\contrib\testrunner /Y
copy jprops.py C:\Python27\Lib\site-packages\robotide\contrib\testrunner /Y
copy testrunner.py C:\Python27\Lib\site-packages\robotide\contrib\testrunner /Y