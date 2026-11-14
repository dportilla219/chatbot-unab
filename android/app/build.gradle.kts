plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "co.edu.unab.chatbot"
    compileSdk = 35
    defaultConfig {
        applicationId = "co.edu.unab.chatbot"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
        // URL de la app Gradio desplegada en EC2 (cámbiala por la tuya)
        buildConfigField("String", "APP_URL", "\"https://app.CAMBIA-IP.sslip.io\"")
    }
    buildFeatures { buildConfig = true }
    buildTypes { release { isMinifyEnabled = false } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
}
