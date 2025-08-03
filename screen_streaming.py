#!/opt/miniforge/bin/python

import cv2
import socket
import struct
import numpy as np
import dbus
import dbus.mainloop.glib
import uuid
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import time
import zlib

UDP_IP = "192.168.0.109"
UDP_PORT = 5600
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

CHUNK_SIZE = 32767
HEADER_INDICATOR = -114514


# === GLOBALS ===
app_id = "com.example.ScreenCapture"
token = 'screencast_' + uuid.uuid4().hex[:8]
real_session_handle = None
node_id = None
Gst.init(None)
loop = GLib.MainLoop()

# === DBus Setup ===
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
proxy = bus.get_object('org.freedesktop.portal.Desktop',
                       '/org/freedesktop/portal/desktop')
interface = dbus.Interface(proxy, 'org.freedesktop.portal.ScreenCast')

# === Portal Signal Handler ===
def on_signal(response, results, path=None):
    global real_session_handle, node_id

    if response != 0:
        print("Portal request failed:", response)
        loop.quit()
        return

    if 'session_handle' in results:
        real_session_handle = results['session_handle']
        print("Session handle received:", real_session_handle)
        select_sources()

    elif 'streams' in results:
        for stream in results['streams']:
            node_id = int(stream[0])
            print("Received PipeWire node ID:", node_id)
        loop.quit()  # Exit GLib loop, ready to start OpenCV

# === DBus Request Steps ===
def create_session():
    print("Creating session...")
    interface.CreateSession({
        'session_handle_token': dbus.String(token)
    },
        reply_handler=lambda r: print("CreateSession request sent"),
        error_handler=lambda e: print("CreateSession error:", e)
    )

def select_sources():
    print("Selecting sources...")
    interface.SelectSources(
        real_session_handle,
        {
            'types': dbus.UInt32(1),  # 1 = Monitor only
            'multiple': dbus.Boolean(False),
        },
        reply_handler=lambda r: print("SelectSources request sent"),
        error_handler=lambda e: print("SelectSources error:", e)
    )
    GLib.timeout_add(1500, start_screencast)

def start_screencast():
    print("Starting screencast...")
    interface.Start(
        real_session_handle,
        app_id,
        {},
        reply_handler=lambda r: print("Start request sent"),
        error_handler=lambda e: print("Start error:", e)
    )
    return False  # So timeout_add only runs once


def send_frame_udp(jpg_bytes: bytes, udp_ip=UDP_IP, udp_port=UDP_PORT, sock_inst=sock):
    data = jpg_bytes
    frame_len = len(data)
    num_chunks = (frame_len + CHUNK_SIZE - 1) // CHUNK_SIZE
    checksum = zlib.crc32(data)

    # header
    header = struct.pack(">iii", HEADER_INDICATOR, frame_len, checksum // 100)
    sock_inst.sendto(header, (udp_ip, udp_port))
    
    for i in range(num_chunks):
        chunk = data[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        sock_inst.sendto(chunk, (udp_ip, udp_port))

# callback function for gst pipeline
def on_new_sample(sink):
    sample = sink.emit("pull-sample")
    if sample is None:
        print("No sample received")
        return

    caps = sample.get_caps()
    structure = caps.get_structure(0)
    width = structure.get_value("width")
    height = structure.get_value("height")
    fmt = structure.get_value("format")

    buf = sample.get_buffer()
    data = buf.extract_dup(0, buf.get_size())

    if fmt == "RGB":
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
    elif fmt == "BGR":
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
    elif fmt == "BGRA":
        frame_bgra = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        frame = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
    elif fmt == "GRAY8":
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    
    success, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
    if not success:
        return Gst.FlowReturn.ERROR

    data = jpg.tobytes()

    send_frame_udp(data)

    return Gst.FlowReturn.OK

# === GStreamer + OpenCV Pipeline ===
def run_opencv_stream(node_id):
    empty_dict = dbus.Dictionary(signature="sv")
    fd_object = proxy.OpenPipeWireRemote(real_session_handle, empty_dict,
                                          dbus_interface='org.freedesktop.portal.ScreenCast')
    fd = fd_object.take()
    print(f"fd: {fd}, node: {node_id}")
    gst_pipeline_str = (f"pipewiresrc fd={fd} path={node_id} ! videoconvert ! appsink name=sink emit-signals=true sync=false")
    print("Starting OpenCV GStreamer pipeline...")
    pipeline = Gst.parse_launch(gst_pipeline_str)
    appsink = pipeline.get_by_name("sink")
    appsink.connect("new-sample", on_new_sample)
    pipeline.set_state(Gst.State.PLAYING)
    try:
        bus = pipeline.get_bus()
        while True:
            # time.sleep(0.1)
            msg = bus.timed_pop_filtered(100 * Gst.MSECOND, Gst.MessageType.ANY)
            if msg and msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                print(f"GStreamer 错误: {err}, {debug}")
                break
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        sock.close()



# === Signal receiver ===
bus.add_signal_receiver(
    on_signal,
    signal_name='Response',
    dbus_interface='org.freedesktop.portal.Request',
    path_keyword='path'
)

# === Run GLib loop in main thread ===
create_session()
print("Waiting for user to confirm screen selection...")
loop.run()

# === Run OpenCV after session is ready ===
if node_id is not None:
    run_opencv_stream(node_id)
else:
    print("No node_id received, cannot start OpenCV stream.")
