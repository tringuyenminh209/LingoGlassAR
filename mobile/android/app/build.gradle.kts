plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.lingoglass.lingoglass_mobile"
    compileSdk = flutter.compileSdkVersion
    // flutter_sound 9.30+ ships native binaries built against NDK 27.
    // All other plugins (flutter_blue_plus_android, path_provider_android,
    // permission_handler_android, shared_preferences_android) also expect 27.
    ndkVersion = "27.0.12077973"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.lingoglass.lingoglass_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        //minSdk = flutter.minSdkVersion
        // 24 required by flutter_sound 9.30+ (was 21 for BLE-only S0).
        // Android 7.0 covers ~99% of devices in 2026; safe bump.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    // S3 OCR: the google_mlkit_text_recognition plugin bundles only the Latin
    // model and declares the Japanese/Chinese/Korean/Devanagari scripts as
    // `compileOnly` to keep app size down. We use TextRecognitionScript.japanese
    // (lib/ocr/ocr_scanner.dart), so the app must add the Japanese runtime model
    // itself — without this the APK compiles but throws ClassNotFoundException
    // for JapaneseTextRecognizerOptions$Builder at first capture. Version pinned
    // to match the plugin's own dependency (text-recognition:16.0.1).
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
}
