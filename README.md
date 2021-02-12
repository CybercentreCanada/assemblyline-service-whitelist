# Whitelisting service

This service allow you to whitelist a set of files so they do not get scan by assemblyline anymore. 

In it's current state, it can import hashes from any URL as long as the file on the other end has the same CSV format then NSRL. Which means that if you point the updater to an API endpoint or another file that has that same CSV format, the resulting hashes would be able to be whitelisted as well.

#### Origin

This service was born from post by Godfried on Assemblyline's Google Groups.

https://groups.google.com/g/cse-cst-assemblyline/c/1LfGQeSoZWQ/m/PYDGf2NkBAAJ

#### _Future_ 

_We might want to look at creating a whitelisting feature directly inside Assemblyline's UI and point the updater for this service to that endpoint that way AL could have its own built-in whitelisting feature._ 