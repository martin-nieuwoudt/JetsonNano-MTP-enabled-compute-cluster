import sys, time
sys.path.insert(0, r"C:\Users\marti\Desktop\Cluster\code")
import cluster_telemetry as ct

t0 = time.time()
state = ct.collect_state()
dt = time.time() - t0
for n in state["nodes"]:
    print(n["ip"], n["status"], "rpc=", n["rpc"], "ram=", round(n["ram_gb"], 2), n["errors"])
print(f"-- collect_state took {dt:.1f}s --")
