# ADN Socket 實驗工作區

本工作區包含兩個 UDP Socket 網路傳輸與代理（Proxy）實驗情境，並已建立 `.env` Python 虛擬環境完成實測與量化分析：

1. **[scenario1_udp_proxy_chain/]( ./scenario1_udp_proxy_chain/README.md )** — 情境一：多程序 UDP 代理串聯轉發 (`Client -> Proxy1 -> Proxy2 -> Server`)
2. **[scenario2_udp_multipath_sim/]( ./scenario2_udp_multipath_sim/README.md )** — 情境二：多路徑 UDP 掉包、延遲與批次重傳模擬 (`Q3.py`, `Q4.py`, `text.py`)

## 環境建立

```bash
python -m venv .env
# Windows: .env\Scripts\activate    Linux/macOS: source .env/bin/activate
pip install -r requirements.txt
```
