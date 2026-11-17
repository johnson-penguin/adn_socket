# 情境一：多程序 UDP 代理串聯轉發 — 量化測試報告

## 1. 測試環境與拓撲架構

- **執行環境**：Python 虛擬環境 (`.env`)
- **節點與埠號配置**：
  - `client.py`：UDP Client（動態綁定本機埠號，目標 `127.0.0.1:8888`）
  - `proxy1.py`：綁定 `127.0.0.1:8888`，轉發至 `127.0.0.1:8889`
  - `proxy2.py`：綁定 `127.0.0.1:8889`，將字串轉為大寫 (`.upper()`) 後轉發至 `127.0.0.1:12345`
  - `server.py`：綁定 `127.0.0.1:12345`，接收後將原封包回傳給發送方位址 (`client_address`)

```text
[Client] ──(100 筆, 每 0.1s)──> [Proxy1 :8888] ──> [Proxy2 :8889] <══(無限乒乓迴圈)══> [Server :12345]
   ▲
   └── (阻塞等待 Proxy1 回傳，永不結束)
```

---

## 2. 量化實測數據（測試視窗：11.5 秒）

| 量化指標 | 設定值 / 預期值 | 實測數值 | 狀態與說明 |
| :--- | :---: | :---: | :--- |
| **Client 發送封包總數** | 100 筆 | **100 筆** | 每筆間隔 `0.1s`，共耗時約 `9.9s` 發送完畢 |
| **Client 單筆封包大小** | 67 ~ 69 Bytes | **67 ~ 69 Bytes** | 內容：`"UDP Server sends Packet i to UDP Client as the i-th transmission."` |
| **Proxy1 (`:8888`) 接收並轉發數** | 100 筆 | **100 筆 (100%)** | 完整接收 Client 的 100 筆封包並轉發至 Proxy2 |
| **Proxy2 (`:8889`) 大寫轉換率** | 100% | **100%** | 成功轉為 `"UDP SERVER SENDS PACKET ..."` |
| **Server (`:12345`) 11.5 秒內接收總數** | 100 筆 | **400,592 筆** (~34,834 封包/秒) | **異常暴增**：因 `Server` 與 `Proxy2` 發生無限回音風暴 (Echo Storm) |
| **Client 接收到回傳封包數** | 1 筆 | **0 筆** | `client.py` 卡在第 16 行 `client_socket.recvfrom(1024)` 永久阻塞 |

---

## 3. 實測發現之關鍵問題分析

### 問題一：`Proxy2` 與 `Server` 之間的 UDP 無限迴圈風暴（11.5 秒產生 40 萬筆封包）
1. 在 `server.py` 第 15–17 行：
   ```python
   data, client_address = server_socket.recvfrom(1024)
   server_socket.sendto(data, client_address)
   ```
   因為封包是由 `Proxy2` (`127.0.0.1:8889`) 發送給 `Server`，所以 `Server` 看到的 `client_address` 是 `('127.0.0.1', 8889)`（即 `Proxy2`），並將封包回傳給 `Proxy2`。
2. 在 `proxy2.py` 第 11–13 行：
   ```python
   proxy1_data, proxy1_address = proxy2_socket.recvfrom(1024)
   modified_data = proxy1_data.decode('utf-8').upper().encode('utf-8')
   proxy2_socket.sendto(modified_data, server_address)
   ```
   `Proxy2` 並未檢查來源位址 `proxy1_address` 是否為 `Proxy1`，因此當它收到 `Server` 回傳的封包時，誤以為是新的封包，再次轉成大寫送回給 `Server` (`127.0.0.1:12345`)，形成本機迴路風暴（實測每秒來回約 **3.48 萬次**）。

### 問題二：`Client` 永久阻塞於 `recvfrom(1024)`
- `client.py` 第 16 行執行 `data, _ = client_socket.recvfrom(1024)` 等待回應，且未設定 `settimeout()`。
- 由於 `Proxy2` 與 `Proxy1` 皆只實作了單向轉發（`Client -> Proxy1 -> Proxy2 -> Server`），沒有將 `Server` 的回應沿原路（`Server -> Proxy2 -> Proxy1 -> Client`）傳回給 `Client`，導致 `client.py` 發完 100 筆封包後永久卡住無法結束。
