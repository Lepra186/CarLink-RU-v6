#!/usr/bin/env python3
"""Reproducibly integrate two upstream projects for an experimental debug build.

Inputs: cloned ./source/carlink and ./source/airplay.
This is an integration candidate, not evidence of functional CarPlay/AirPlay.
"""
from pathlib import Path
import shutil
import re

root = Path("source/carlink")
airplay = Path("source/airplay")
assert (root / "settings.gradle.kts").is_file()
assert (airplay / "app/src/main/cpp/CMakeLists.txt").is_file()
destination = root / "airplay-receiver"
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(airplay / "app", destination, ignore=shutil.ignore_patterns("build", ".cxx"))

def change(path, old, new):
    file = root / path
    data = file.read_text()
    if old not in data:
        raise RuntimeError(f"Upstream changed, missing patch anchor {old[:80]!r} in {path}")
    file.write_text(data.replace(old, new, 1))

def write(path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)

# AGP 9 uses built-in Kotlin support, so do not apply the older Kotlin Android plugin.
# Keep the original Kotlin, Compose, native JNI/UxPlay and media decoder source.
write("airplay-receiver/build.gradle.kts", r'''plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.compose)
}
android {
    namespace = "io.github.jqssun.airplay"
    compileSdk { version = release(37) }
    ndkVersion = "27.0.12077973"
    defaultConfig {
        minSdk = 28
        externalNativeBuild { cmake { arguments += "-DANDROID_STL=c++_shared" } }
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }
    externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt") } }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
}
dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.0")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("androidx.media:media:1.7.0")
    implementation(libs.androidx.media3.exoplayer)
    implementation(libs.androidx.media3.ui)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation("androidx.compose.material:material-icons-extended")
}
''')
# Keep upstream compileSdk 37 (Android 17) so CarPlay permission constants and
# current Compose AAR metadata remain compatible. The CI installs android-37.0.
# Android 10 compatibility is governed by the original minSdk, not compileSdk.

change("settings.gradle.kts", 'include(":app")', 'include(":app")\ninclude(":airplay-receiver")')
# AirPlay's native dependency requires at least API 28. TEYES Android 10 is API 29.
# Raise the host minSdk rather than using an unsafe manifest override.
change("app/build.gradle.kts", 'minSdk = 25', 'minSdk = 28')
change("app/build.gradle.kts", 'implementation(project(":carlink-core"))', 'implementation(project(":carlink-core"))\n    implementation(project(":airplay-receiver"))')
# Remove upstream English-only filter so resource qualifiers (including Russian) work.
change("app/build.gradle.kts", 'localeFilters += listOf("en")', 'localeFilters += listOf("en", "ru")')
# The old AirPlay manifest defined its own Application and launcher; the CarLink app
# must remain the sole Android application/launcher.
manifest = destination / "src/main/AndroidManifest.xml"
s = manifest.read_text()
s = re.sub(r'<application\b[^>]*>', '<application android:usesCleartextTraffic="true">', s, count=1, flags=re.S)
s = re.sub(r'\s*<intent-filter>[\s\S]*?</intent-filter>', '', s, count=1)  # AirPlay launcher
s = re.sub(r'\s*<receiver\b[^>]*android:name="\.BootReceiver"[\s\S]*?</receiver>', '', s)
manifest.write_text(s)
# Hilt was only used for Application, Activity and ViewModel scaffolding;
# use Android's built-in ViewModel factory for the AndroidViewModel(Application).
appkt = destination / "src/main/kotlin/io/github/jqssun/airplay/AirPlayApp.kt"
appkt.unlink()
for filename in destination.rglob("*.kt"):
    s = filename.read_text()
    s = re.sub(r'^import (dagger\.hilt\.[^\n]+|javax\.inject\.Inject)\n', '', s, flags=re.M)
    s = re.sub(r'^\s*@(AndroidEntryPoint|HiltViewModel|HiltAndroidApp)\s*\n', '\n', s, flags=re.M)
    s = s.replace("@Inject constructor(", "constructor(")
    filename.write_text(s)

# Kotlin 2.4 correctly treats MediaProjectionManager.getMediaProjection() as nullable.
# Abort the sender service when capture permission does not yield a projection.
sender = destination / "src/main/kotlin/io/github/jqssun/airplay/mirror/MirrorSenderService.kt"
sender_source = sender.read_text()
projection_anchor = "projection = mpm.getMediaProjection(resultCode, data).also {"
if projection_anchor not in sender_source:
    raise RuntimeError("MediaProjection upstream anchor changed")
sender.write_text(sender_source.replace(projection_anchor,
    "projection = (mpm.getMediaProjection(resultCode, data) ?: run { stopSelf(); return START_NOT_STICKY }).also {", 1))

# Native activity of the actual AirPlay receiver is launched from within CarLink.
# Stop CarPlay first, releasing the transport before starting mDNS & video decoding.
path = "app/src/main/java/com/carlink/app/ui/HomeActivity.kt"
change(path,
    'CarLinkApp(vm, onExitToCarHome = ::exitToCarHome)',
    '''CarLinkApp(vm, onExitToCarHome = ::exitToCarHome)
                    androidx.compose.material3.Button(
                        onClick = {
                            Connection.get(this@HomeActivity).stop()
                            startActivity(Intent(this@HomeActivity,
                                io.github.jqssun.airplay.MainActivity::class.java))
                        },
                        modifier = androidx.compose.ui.Modifier
                            .align(androidx.compose.ui.Alignment.BottomEnd)
                            .padding(androidx.compose.ui.unit.Dp(16f))
                    ) { androidx.compose.material3.Text("AirPlay") }''')
change(path, 'import android.os.Bundle', 'import android.os.Bundle\nimport androidx.compose.foundation.layout.padding')
# Clear receiver state on exit and return to the integrated CarLink Home.
main = destination / "src/main/kotlin/io/github/jqssun/airplay/MainActivity.kt"
s = main.read_text()
anchor = '''                MainScreen(
                    viewModel = viewModel,'''
replacement = '''                androidx.compose.foundation.layout.Box {
                MainScreen(
                    viewModel = viewModel,'''
if anchor not in s:
    raise RuntimeError("AirPlay MainScreen anchor changed")
s = s.replace(anchor, replacement, 1)
anchor2 = '''                    onPip = { enterPip() }
                )'''
replacement2 = '''                    onPip = { enterPip() }
                )
                androidx.compose.material3.Button(
                    onClick = {
                        service?.stopServer()
                        finish()
                    },
                    modifier = androidx.compose.ui.Modifier
                        .align(androidx.compose.ui.Alignment.TopEnd)
                        .padding(androidx.compose.ui.unit.Dp(12f))
                ) { androidx.compose.material3.Text("CarPlay / Назад") }
                }'''
if anchor2 not in s:
    raise RuntimeError("AirPlay button anchor changed")
s = s.replace(anchor2, replacement2, 1)
s = s.replace('import android.Manifest', 'import android.Manifest\nimport androidx.compose.foundation.layout.padding')
main.write_text(s)

# Preserve the AirPlay source's GPL notices and expose Russian mode labels.
ru_dir = destination / "src/main/res/values-ru"
ru_dir.mkdir(parents=True, exist_ok=True)
(ru_dir / "carlink_ru.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<resources><string name="app_name">CarLink RU — AirPlay</string></resources>\n'
)
print("Integration candidate assembled at source/carlink; compile and device tests required.")
