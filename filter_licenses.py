import csv
import re
from pathlib import Path

# 【修复】防止字段过长报错
csv.field_size_limit(2147483647)

# 定义允许的许可证列表（白名单）
# 全部转为小写，用于比对
ALLOWED_LICENSES = {
    'mit', 'apache-2.0', 'bsd-2-clause', 'bsd-3-clause',
    'isc', 'zlib', 'bsl-1.0', 'cc0-1.0',
    'python', 'bsd', 'bsd-zero', 'bsd-new',
    'bsd-new or apache-2.0',
    'apache-2.0 and mit',
    'bsd-simplified', 'zpl-2.1'
}


def clean_text(text):
    """
    暴力清洗文本：
    1. 去除所有不可见字符（换行、回车、制表符）
    2. 将连续空格合并为一个空格
    3. 去除首尾空格
    4. 统一转小写
    """
    if not text:
        return ""
    # 替换所有空白字符为普通空格
    text = re.sub(r'\s+', ' ', text)
    # 去除首尾空格并转小写
    return text.strip().lower()


def filter_licenses(input_file, output_file):
    print(f"🔍 正在读取: {input_file}")

    kept_count = 0  # 保留行数（需要关注的）
    filtered_count = 0  # 过滤行数（白名单或空值）

    # 尝试多种编码读取
    encodings = ['utf-8-sig', 'utf-8', 'gbk']
    rows = None
    used_encoding = ''

    for enc in encodings:
        try:
            with open(input_file, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                fieldnames = reader.fieldnames
                used_encoding = enc
                break
        except Exception:
            continue

    if rows is None:
        print("❌ 无法读取文件，请检查文件编码或路径")
        return

    # 自动识别第三列的列名
    target_col = None
    if len(fieldnames) >= 3:
        target_col = fieldnames[2]
        print(f"🎯 锁定第三列作为筛选目标: [{target_col}]")
    else:
        print("❌ 文件列数不足3列")
        return

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            raw_val = row.get(target_col, "")
            clean_val = clean_text(raw_val)

            # --- 核心逻辑 ---

            # 1. 如果是空值（清洗后为空字符串），直接过滤掉
            if clean_val == "":
                filtered_count += 1
                continue

            # 2. 如果清洗后的值在白名单中，过滤掉
            if clean_val in ALLOWED_LICENSES:
                filtered_count += 1
                continue

            # 3. 其他情况（包括串联的、未知的），保留
            writer.writerow(row)
            kept_count += 1

    print(f"✅ 处理完成！")
    print(f"   原始记录数: {len(rows)}")
    print(f"   过滤行数 (白名单+空值): {filtered_count}")
    print(f"   保留行数 (需关注): {kept_count}")
    print(f"   结果已保存至: {output_file}")


if __name__ == '__main__':
    base_dir = Path(__file__).parent
    input_path = base_dir / "scancode_reports" / "scancode_report_full.csv"
    output_path = base_dir / "scancode_reports" / "scancode_report_filtered.csv"

    if not input_path.exists():
        print(f"❌ 找不到输入文件: {input_path}")
    else:
        filter_licenses(str(input_path), str(output_path))