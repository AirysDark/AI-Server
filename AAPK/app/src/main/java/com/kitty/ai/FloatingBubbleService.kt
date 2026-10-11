package com.kitty.ai

import android.annotation.SuppressLint
import android.app.*
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.view.*
import android.widget.ImageView
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.Rect
import androidx.core.app.NotificationCompat
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import kotlin.math.abs

class FloatingBubbleService : Service() {

    private lateinit var windowManager: WindowManager
    private var floatingView: View? = null
    private val handler = Handler(Looper.getMainLooper())
    private val executor = Executors.newSingleThreadExecutor()
    
    private var lastActivity: Long = System.currentTimeMillis()
    private val pollInterval: Long = 30000 // 30 seconds
    private var isAppInForeground = false
    private var currentPhotoUrl: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP_SERVICE") {
            stopSelf()
            return START_NOT_STICKY
        }
        
        if (intent?.action == "REFRESH_ICON") {
            updateBubbleIcon()
            return START_STICKY
        }
        
        isAppInForeground = intent?.getBooleanExtra("EXTRA_FOREGROUND", false) ?: false
        
        createNotificationChannel()
        val notification = createForegroundNotification("Assistant is active")
        startForeground(1, notification)

        if (floatingView == null) {
            setupFloatingBubble()
        }
        
        floatingView?.visibility = if (isAppInForeground) View.GONE else View.VISIBLE

        updateBubbleIcon()
        startPolling()
        
        return START_STICKY
    }

    private fun setupFloatingBubble() {
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        floatingView = LayoutInflater.from(this).inflate(R.layout.layout_floating_bubble, null)

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        )

        params.gravity = Gravity.TOP or Gravity.START
        params.x = 100
        params.y = 100

        val bubbleIcon = floatingView!!.findViewById<ImageView>(R.id.bubble_icon)
        bubbleIcon.setImageResource(R.drawable.ic_ai_bubble)

        floatingView!!.setOnTouchListener(object : View.OnTouchListener {
            private var initialX: Int = 0
            private var initialY: Int = 0
            private var initialTouchX: Float = 0.0f
            private var initialTouchY: Float = 0.0f

            @SuppressLint("ClickableViewAccessibility")
            override fun onTouch(v: View?, event: MotionEvent?): Boolean {
                when (event?.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initialX = params.x
                        initialY = params.y
                        initialTouchX = event.rawX
                        initialTouchY = event.rawY
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        params.x = initialX + (event.rawX - initialTouchX).toInt()
                        params.y = initialY + (event.rawY - initialTouchY).toInt()
                        windowManager.updateViewLayout(floatingView, params)
                        return true
                    }
                    MotionEvent.ACTION_UP -> {
                        val diffX = abs(event.rawX - initialTouchX)
                        val diffY = abs(event.rawY - initialTouchY)
                        if (diffX < 10 && diffY < 10) {
                            openApp()
                        }
                        return true
                    }
                }
                return false
            }
        })

        windowManager.addView(floatingView, params)
    }

    private fun updateBubbleIcon() {
        val prefs = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
        val photoUrl = prefs.getString("profile_photo", "") ?: ""
        val cookies = prefs.getString("cookies", "") ?: ""
        
        if (photoUrl.isEmpty() || photoUrl == currentPhotoUrl) return
        
        currentPhotoUrl = photoUrl
        executor.execute {
            try {
                val url = URL(photoUrl)
                val connection = url.openConnection() as HttpURLConnection
                connection.doInput = true
                if (cookies.isNotEmpty()) {
                    connection.setRequestProperty("Cookie", cookies)
                }
                connection.connect()
                val input = connection.inputStream
                val bitmap = BitmapFactory.decodeStream(input)
                if (bitmap != null) {
                    val circularBitmap = getCircleBitmap(bitmap)
                    handler.post {
                        val bubbleIcon = floatingView?.findViewById<ImageView>(R.id.bubble_icon)
                        bubbleIcon?.setImageBitmap(circularBitmap)
                    }
                }
            } catch (e: Exception) {
                handler.post {
                    val bubbleIcon = floatingView?.findViewById<ImageView>(R.id.bubble_icon)
                    bubbleIcon?.setImageResource(R.drawable.ic_ai_bubble)
                }
            }
        }
    }

    private fun getCircleBitmap(bitmap: Bitmap): Bitmap {
        val output = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(output)
        val color = -0xbdbdbe
        val paint = Paint()
        val rect = Rect(0, 0, bitmap.width, bitmap.height)
        paint.isAntiAlias = true
        canvas.drawARGB(0, 0, 0, 0)
        paint.color = color
        canvas.drawCircle((bitmap.width / 2).toFloat(), (bitmap.height / 2).toFloat(), (bitmap.width / 2).toFloat(), paint)
        paint.xfermode = PorterDuffXfermode(PorterDuff.Mode.SRC_IN)
        canvas.drawBitmap(bitmap, rect, rect, paint)
        return output
    }

    private fun openApp() {
        val intent = Intent(this, MainActivity::class.java)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }

    private fun startPolling() {
        handler.removeCallbacksAndMessages(null)
        handler.postDelayed(object : Runnable {
            override fun run() {
                if (!isAppInForeground) {
                    checkProactiveMessages()
                    updateBubbleIcon()
                }
                handler.postDelayed(this, pollInterval)
            }
        }, pollInterval)
    }

    private fun checkProactiveMessages() {
        executor.execute {
            try {
                val prefs = getSharedPreferences("LocalAIPrefs", Context.MODE_PRIVATE)
                val defaultUrl = "http://ai-server.ddns.net"
                val serverUrl = prefs.getString("server_url", defaultUrl) ?: defaultUrl
                val cookies = prefs.getString("cookies", "") ?: ""
                
                if (serverUrl.isEmpty() || cookies.isEmpty()) return@execute

                val url = URL("$serverUrl/api/proactive?last_activity=$lastActivity")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.setRequestProperty("Cookie", cookies)
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                if (connection.responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(response)
                    val message = json.optString("message", "")
                    val imageUrl = json.optString("image", "")
                    
                    if ((message.isNotEmpty() && message != "null") || (imageUrl.isNotEmpty() && imageUrl != "null")) {
                        showNotification("Local AI", message, imageUrl)
                        lastActivity = System.currentTimeMillis()
                    }
                }
            } catch (e: Exception) {
                // Silently ignore connection errors in background
            }
        }
    }

    private fun showNotification(title: String, text: String, imageUrl: String = "") {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(this, "ai_messages")
            .setSmallIcon(R.drawable.ic_ai_bubble)
            .setContentTitle(title)
            .setContentText(if (text.isEmpty() && imageUrl.isNotEmpty()) "Sent you a photo" else text)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)

        if (imageUrl.isNotEmpty()) {
            builder.setSubText("Attached Image")
        }

        val notificationManager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(System.currentTimeMillis().toInt(), builder.build())
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "ai_messages",
                "Local AI Messages",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifications for AI chat messages"
            }
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
            
            val foregroundChannel = NotificationChannel(
                "ai_service",
                "Local AI Background Service",
                NotificationManager.IMPORTANCE_LOW
            )
            notificationManager.createNotificationChannel(foregroundChannel)
        }
    }

    private fun createForegroundNotification(text: String): Notification {
        val stopIntent = Intent(this, FloatingBubbleService::class.java).apply {
            action = "STOP_SERVICE"
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, "ai_service")
            .setSmallIcon(R.drawable.ic_ai_bubble)
            .setContentTitle("Local AI")
            .setContentText(text)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop Bubble", stopPendingIntent)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        floatingView?.let { windowManager.removeView(it) }
        handler.removeCallbacksAndMessages(null)
    }
}
