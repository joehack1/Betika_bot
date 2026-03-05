[app]
title = Betika Mobile Remote
package.name = betikamobile
package.domain = org.betikabot
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,json,txt
version = 0.1.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.archs = arm64-v8a, armeabi-v7a
android.api = 33
android.minapi = 24

[buildozer]
log_level = 2
warn_on_root = 1
