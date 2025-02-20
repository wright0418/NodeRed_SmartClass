import json

def colonize(mac):
    # 將每兩位數字加上冒號
    return ":".join(mac[i:i+2] for i in range(0, len(mac), 2))

def main():
    # 新增：從用戶取得輸入與輸出檔名
    input_file = input("請輸入輸入檔名: ")
    output_file = input("請輸入輸出檔名: ")
    
    # 使用用戶輸入的檔名讀取資料
    with open(input_file, "r", encoding="utf-8") as f:
        devices_data = json.load(f)
    
    devices_list = []
    for dev in devices_data.values():
        devices_list.append({
            "devMac": colonize(dev["mac_addr"]),
            "devName": "",
            "devType": dev["name"],
            "devPosition": "",
            "devGroup": "",
            "uid": dev["uid"],
            "state": 1 if dev["state"] == 5 else dev["state"]
        })
    
    # 嘗試讀取輸出檔案的 header 資訊（若存在）
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            new_dev_template = json.load(f)
    except FileNotFoundError:
        new_dev_template = {"gwMac": "", "gwType": "mini_PC", "gwPosition": "主機位置"}
    
    new_dev_template["devices"] = devices_list
    
    # 寫入結果到用戶指定的輸出檔名
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(new_dev_template, f, ensure_ascii=False, indent=4)
    
if __name__ == "__main__":
    main()
