# ADN Socket 實驗工作區

本工作區包含兩個 UDP Socket 網路傳輸與代理（Proxy）實驗情境，皆已修復原始程式的問題，並完成實測與量化分析：

1. **[scenario1_udp_proxy_chain/]( ./scenario1_udp_proxy_chain/README.md )** — 情境一：多程序 UDP 代理串聯轉發 (`Client -> Proxy1 -> Proxy2 -> Server`)
2. **[scenario2_udp_multipath_sim/]( ./scenario2_udp_multipath_sim/README.md )** — 情境二：多路徑 UDP 掉包、延遲與批次重傳模擬
   - [q3_loss_delay_measure/]( ./scenario2_udp_multipath_sim/q3_loss_delay_measure/README.md ) — `Q3.py`：單筆傳輸的掉包率與延遲率量測
   - [q4_batch_multipath_retransmit/]( ./scenario2_udp_multipath_sim/q4_batch_multipath_retransmit/README.md ) — `Q4.py`、`text.py`：批次傳輸、雙路徑分流與掉包重傳

## 環境建立

```bash
python -m venv .env
# Windows: .env\Scripts\activate    Linux/macOS: source .env/bin/activate
pip install -r requirements.txt
```

本專案只使用 Python 標準函式庫，測試環境為 Windows 11、Python 3.10.6。

---

## 代表性實驗結果

| 情境 | 修復前 | 修復後 | 詳細 |
| :--- | :--- | :--- | :--- |
| **情境一** 代理串聯 | Proxy2 ↔ Server 無限迴圈（11.5 秒 40 萬筆），Client 永久阻塞 | Client 收齊 100 / 100 筆，約 11 秒正常結束 | [驗證結果](./scenario1_udp_proxy_chain/README.md#5-修復後驗證結果) |
| **Q3** 掉包 / 延遲量測 | 印出結果後卡住；Path 3 除以零崩潰 | 三條路徑皆正常結束，掉包率 22%（設定 20%）、延遲率 50%（設定 50%） | [驗證結果](./scenario2_udp_multipath_sim/q3_loss_delay_measure/README.md#5-修復後驗證結果100-筆) |
| **Q4** 批次與重傳 | 重傳流程不通，遺失的封包無法補回 | 所有路徑與模式皆收齊，100% 掉包也能全部重傳補回 | [驗證結果](./scenario2_udp_multipath_sim/q4_batch_multipath_retransmit/README.md#5-修復後驗證結果) |

### 十萬筆封包最快傳輸：5.6 秒

```bash
python Q4.py 2 2 --packets=100000 --group=2977 --rcvbuf=1048576
```

| 設定（Path 2、傳送間隔 0.1 秒） | 耗時 |
| :--- | ---: |
| 每批 10 筆（原始設定，推算） | 約 1,000 s |
| 每批 2,977 筆（UDP 單一封包上限） | 7.7 ~ 9.9 s |
| **每批 2,977 筆 + 接收緩衝區 1 MB** | **5.6 s** |

- 一批最多 **2,977 筆**，受 UDP 單一封包 65,507 bytes 限制。
- Windows 預設 64 KB 接收緩衝區會在 Proxy2 延遲時溢出、被作業系統丟包；加大到 **1 MB** 即可消除。

詳細測試過程與數據：[批次大小測試](./scenario2_udp_multipath_sim/q4_batch_multipath_retransmit/README.md#8-十萬筆封包批次大小測試)、[結論](./scenario2_udp_multipath_sim/q4_batch_multipath_retransmit/README.md#87-結論)。路線比例與分流方式的實驗見 [多情境實驗](./scenario2_udp_multipath_sim/q4_batch_multipath_retransmit/README.md#7-多情境實驗路線與分流比例)。
