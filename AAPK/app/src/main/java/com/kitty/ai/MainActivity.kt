package com.kitty.ai

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.*
import android.widget.*
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var configLayout: LinearLayout
    private lateinit var serverUrlInput: EditText
    private lateinit var btnApply: Button
    private lateinit var btnReset: Button
    private lateinit var errorText: TextView
    private lateinit var loadingProgress: ProgressBar

    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    private val requestNotificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (!isGranted) {
            Toast.makeText(this, "Permission denied", Toast.LENGTH_SHORT).show()
        }
    }

    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (Settings.canDrawOverlays(this)) {
                startFloatingService()
            }
        }
    }

    private val fileChooserLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val data: Intent? = result.data
            val results = WebChromeClient.FileChooserParams.parseResult(result.resultCode, data)
            filePathCallback?.onReceiveValue(results)
        } else {
            filePathCallback?.onReceiveValue(null)
        }
        filePathCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        configLayout = findViewById(R.id.config_layout)
        serverUrlInput = findViewById(R.id.server_url_input)
        btnApply = findViewById(R.id.btn_apply)
        btnReset = findViewById(R.id.btn_reset)
        errorText = findViewById(R.id.error_text)
        loadingProgress = findViewById(R.id.loading_progress)

        setupWebView()

        val sharedPrefs = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
        val defaultUrl = "https://ai-server.ddns.net"
        var savedUrl = sharedPrefs.getString("server_url", null)

        if (savedUrl.isNullOrEmpty()) {
            savedUrl = defaultUrl
        }

        // Always use the configured server address.
        // If the user wants to see their local dev changes, they must use their local IP.
        loadServer(savedUrl)

        btnApply.setOnClickListener {
            val url = serverUrlInput.text.toString().trim()
            if (url.isNotEmpty()) {
                // Clear cache when manually changing server to avoid stale content
                webView.clearCache(true)
                loadServer(url)
            }
        }

        btnReset.setOnClickListener {
            webView.clearCache(true)
            CookieManager.getInstance().removeAllCookies(null)
            WebStorage.getInstance().deleteAllData()
            val sharedPrefs = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
            sharedPrefs.edit().clear().apply()
            Toast.makeText(this, "App data cleared. Please reconnect.", Toast.LENGTH_SHORT).show()
            showConfig()
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.visibility == View.VISIBLE && webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        checkPermissions()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.databaseEnabled = true
        
        // Handle mixed content
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW

        // Support for LAN addresses
        settings.allowFileAccessFromFileURLs = true
        settings.allowUniversalAccessFromFileURLs = true

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        webView.addJavascriptInterface(WebAppInterface(this), "AndroidApp")

        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                // Only show config if it's the main frame failing
                if (request?.isForMainFrame == true) {
                    val description = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) error?.description else "Connection failed"
                    showConfig("Unable to connect to server: $description")
                }
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                // Optionally show loading on navigation
                // loadingProgress.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                CookieManager.getInstance().flush()
                syncSession()
                injectSyncScript()
                
                // Hide loading progress once page is loaded
                loadingProgress.visibility = View.GONE
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress == 100) {
                    loadingProgress.visibility = View.GONE
                }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback = filePathCallback
                val intent = fileChooserParams?.createIntent()
                try {
                    fileChooserLauncher.launch(intent)
                } catch (e: Exception) {
                    this@MainActivity.filePathCallback = null
                    return false
                }
                return true
            }
        }
    }

    private fun showConfig(error: String? = null) {
        configLayout.visibility = View.VISIBLE
        webView.visibility = View.GONE
        loadingProgress.visibility = View.GONE
        if (error != null) {
            errorText.text = error
            errorText.visibility = View.VISIBLE
        } else {
            errorText.visibility = View.GONE
        }
    }

    private fun loadServer(inputUrl: String) {
        var url = inputUrl.trim()
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "https://$url"
        }
        if (url.endsWith("/")) {
            url = url.substring(0, url.length - 1)
        }

        saveUrl(url)
        configLayout.visibility = View.GONE
        errorText.visibility = View.GONE
        loadingProgress.visibility = View.VISIBLE
        
        // Ensure we load exactly the index.html from the server
        val fullUrl = if (url.endsWith(".html") || url.endsWith(".php")) url else "$url/index.html"
        Log.d("LocalAI", "Loading server URL: $fullUrl")
        webView.visibility = View.VISIBLE
        
        // Force network load for the main entry point to bypass stale cache
        webView.settings.cacheMode = WebSettings.LOAD_NO_CACHE
        webView.loadUrl(fullUrl)
        
        // Restore default cache mode after a delay so subresources can still use cache
        webView.postDelayed({
            webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        }, 5000)
    }

    private fun saveUrl(url: String) {
        val sharedPref = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
        sharedPref.edit().putString("server_url", url).apply()
    }

    private fun injectSyncScript() {
        // This script will periodically check for login state and sync it to Android
        val js = """
            (function() {
                var lastSyncedPhoto = '';
                function sync() {
                    var userId = localStorage.getItem('AI_user');
                    if (!userId) {
                        var match = document.cookie.match(new RegExp('(^| )AI_user=([^;]+)'));
                        if (match) userId = match[2];
                    }
                    var avatar = document.getElementById('avatar');
                    var photoUrl = '';
                    if (avatar && avatar.src && !avatar.src.includes('default.png')) {
                        photoUrl = avatar.src;
                    }
                    var srv = localStorage.getItem('local_ai_server_url') || 'https://ai-server.ddns.net';
                    
                    if (userId || (photoUrl && photoUrl !== lastSyncedPhoto)) {
                        AndroidApp.syncData(userId || '', srv, document.cookie, photoUrl);
                        if (photoUrl) lastSyncedPhoto = photoUrl;
                    }
                }
                
                sync();
                
                // Monitor for photo changes (e.g. after async boot)
                var target = document.getElementById('avatar');
                if (target) {
                    var observer = new MutationObserver(function(mutations) {
                        sync();
                    });
                    observer.observe(target, { attributes: true, attributeFilter: ['src'] });
                }

                // Also sync on interactions
                window.addEventListener('click', sync);
                
                // Add config button
                if (!document.getElementById('android-config-btn')) {
                    var btn = document.createElement('button');
                    btn.id = 'android-config-btn';
                    btn.innerText = 'App Config';
                    btn.style.position = 'fixed';
                    btn.style.top = '5px';
                    btn.style.right = '5px';
                    btn.style.zIndex = '99999';
                    btn.style.background = '#444';
                    btn.style.color = '#fff';
                    btn.style.border = '0';
                    btn.style.borderRadius = '5px';
                    btn.style.padding = '4px 8px';
                    btn.style.fontSize = '10px';
                    btn.style.opacity = '0.7';
                    btn.onclick = function() { AndroidApp.openServerConfig(); };
                    document.body.appendChild(btn);
                }
            })();
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }

    private fun syncSession() {
        val sharedPrefs = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
        val serverUrl = sharedPrefs.getString("server_url", "https://ai-server.ddns.net") ?: "https://ai-server.ddns.net"
        val cookies = CookieManager.getInstance().getCookie(serverUrl) ?: ""
        
        webView.evaluateJavascript("(function() { " +
                "var userId = localStorage.getItem('AI_user');" +
                "if (!userId) {" +
                "  var match = document.cookie.match(new RegExp('(^| )AI_user=([^;]+)'));" +
                "  if (match) userId = match[2];" +
                "}" +
                "var avatar = document.getElementById('avatar');" +
                "var photoUrl = (avatar && avatar.src && !avatar.src.includes('default.png')) ? avatar.src : '';" +
                "return JSON.stringify({ " +
                "userId: userId || '', " +
                "photoUrl: photoUrl " +
                "}); })();") { result ->
            try {
                val json = JSONObject(result.replace("\\\"", "\"").trim('\"'))
                val userId = json.optString("userId")
                val photoUrl = json.optString("photoUrl")
                
                val editor = sharedPrefs.edit()
                val oldPhoto = sharedPrefs.getString("profile_photo", "")
                editor.putString("cookies", cookies)
                if (userId.isNotEmpty()) editor.putString("user_id", userId)
                if (photoUrl.isNotEmpty()) editor.putString("profile_photo", photoUrl)
                editor.apply()

                if (photoUrl.isNotEmpty() && photoUrl != oldPhoto) {
                    val refreshIntent = Intent(this@MainActivity, FloatingBubbleService::class.java)
                    refreshIntent.action = "REFRESH_ICON"
                    startService(refreshIntent)
                }
            } catch (e: Exception) {}
        }
    }

    private fun checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            overlayPermissionLauncher.launch(intent)
        } else {
            startFloatingService()
        }
    }

    private fun startFloatingService() {
        val intent = Intent(this, FloatingBubbleService::class.java)
        intent.putExtra("EXTRA_FOREGROUND", true)
        ContextCompat.startForegroundService(this, intent)
    }

    override fun onResume() {
        super.onResume()
        val intent = Intent(this, FloatingBubbleService::class.java)
        intent.putExtra("EXTRA_FOREGROUND", true)
        startService(intent)
    }

    override fun onPause() {
        super.onPause()
        val intent = Intent(this, FloatingBubbleService::class.java)
        intent.putExtra("EXTRA_FOREGROUND", false)
        startService(intent)
    }

    inner class WebAppInterface(private val mContext: Context) {
        @JavascriptInterface
        fun syncData(userId: String, serverUrl: String, cookies: String, photoUrl: String = "") {
            // Hide progress bar when we receive data, as it means page is active
            runOnUiThread { loadingProgress.visibility = View.GONE }

            if (userId.isEmpty()) {
                // Logout case: stop the floating bubble
                val intent = Intent(mContext, FloatingBubbleService::class.java)
                intent.action = "STOP_SERVICE"
                mContext.startService(intent)
            }

            val sharedPref = mContext.getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
            val oldPhoto = sharedPref.getString("profile_photo", "")
            
            with(sharedPref.edit()) {
                putString("user_id", userId)
                putString("server_url", serverUrl)
                putString("cookies", cookies)
                if (photoUrl.isNotEmpty()) putString("profile_photo", photoUrl)
                apply()
            }

            if (photoUrl.isNotEmpty() && photoUrl != oldPhoto) {
                // Trigger immediate icon refresh
                val refreshIntent = Intent(mContext, FloatingBubbleService::class.java)
                refreshIntent.action = "REFRESH_ICON"
                mContext.startService(refreshIntent)
            }
        }

        @JavascriptInterface
        fun openServerConfig() {
            runOnUiThread { showConfig() }
        }
    }
}
