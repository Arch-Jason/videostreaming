package com.example.videostreaming

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Log
import android.widget.ImageView
import java.io.ByteArrayOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

class MainActivity : Activity() {

    private lateinit var imageView: ImageView
    private val PORT = 5600
    private val CHUNK_SIZE = 32767
    private val HEADER_INDICATOR = -114514

    private var previousBitmap: Bitmap? = null
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        imageView = ImageView(this)
        setContentView(imageView)

        Thread {
            try {
                val socket = DatagramSocket(PORT)
                val headerBuffer = ByteArray(12)
                val chunk = ByteArray(CHUNK_SIZE)
                var previousBitmap: Bitmap? = null

                while (true) {
                    try {
                        // 接收帧头
                        val headerPacket = DatagramPacket(headerBuffer, headerBuffer.size)
                        socket.receive(headerPacket)

                        val header = ByteBuffer.wrap(headerBuffer).order(ByteOrder.BIG_ENDIAN)
                        val headerIndicator = header.int
                        if (headerIndicator != HEADER_INDICATOR) continue
                        val frameLen = header.int
                        val checksum = header.int
                        Log.d("headerIndicator: ", headerIndicator.toString())
                        Log.d("frameLen: ", frameLen.toString())
                        val output = ByteArrayOutputStream()
                        var received = 0

                        while (received < frameLen) {
                            val receiveSize = minOf(CHUNK_SIZE, frameLen - received)
                            val packet = DatagramPacket(chunk, receiveSize)
                            socket.receive(packet)

                            output.write(chunk, 0, packet.length)
                            received += packet.length
                        }

                        val data = output.toByteArray()
                        output.close()

                        // CRC32 校验
                        val crc = CRC32()
                        crc.update(data)
                        val calcCrc = (crc.value / 100).toInt()

                        if (calcCrc != checksum) {
                            Log.e("CRC Error", "Calculated: $calcCrc vs Received: $checksum")
                            continue
                        }

                        // CRC 通过：解码图像
                        val bitmap = BitmapFactory.decodeByteArray(data, 0, data.size)
                        if (bitmap != null) {
                            runOnUiThread {
                                imageView.setImageBitmap(bitmap)
                                previousBitmap?.recycle()
                                previousBitmap = bitmap
                            }
                        } else {
                            println("⚠️ 解码失败")
                        }

                    } catch (e: Exception) {
                        e.printStackTrace()
                        continue
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }.start()
    }
}
