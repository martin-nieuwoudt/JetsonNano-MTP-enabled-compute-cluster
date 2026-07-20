# Windows 11 TCP/IP Auto-Tuning Override for llama.cpp Cluster
# From: raw refinements.md — Section: Windows 11 llama.cpp System Architecture Adjustments
# Run in PowerShell as Administrator on Windows 11 orchestrator.

# Windows 11 defaults to a dynamic TCP window size that throttles outbound
# data streaming if a worker node takes more than a few milliseconds to respond.
netsh int tcp set global autotuninglevel=normal
netsh int tcp set global congestionprovider=ctcp

# ctcp (Compound TCP) optimizes throughput over local high-bandwidth,
# high-latency environments, matching the memory streaming profile
# expected by the Jetson Nanos.