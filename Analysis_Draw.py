import os
import numpy as np
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl

# 设置中文字体支持
mpl.rcParams['font.sans-serif'] = ['SimHei']  # 用黑体显示中文
mpl.rcParams['axes.unicode_minus'] = False  # 正常显示负号

# 配置路径 - 使用原始字符串(r前缀)或双反斜杠
input_dir = r"E:\@WorkSpace\Remote_sense\Carbon\GPP"  # GPP文件夹路径
boundary_path = r"E:\@WorkSpace\Remote_sense\Carbon\SHP\NewJiang.shp"  # 研究区边界
output_dir = r"E:\@WorkSpace\Remote_sense\Carbon\output"  # 输出目录

# 创建输出目录
os.makedirs(output_dir, exist_ok=True)

# 1. 加载研究区边界
gdf = gpd.read_file(boundary_path)
# 确保使用正确的几何对象列表
geometries = [geom for geom in gdf.geometry]

# 2. 处理每年数据
yearly_gpp = []  # 存储每年的平均值
years_processed = []  # 记录成功处理的年份

# 处理2001-2021年数据
for year in range(2001, 2022):
    # 根据文件名格式构建路径
    tif_filename = f"Xinjiang_GPP_{year}.tif"
    tif_path = os.path.join(input_dir, tif_filename)

    # 检查文件是否存在
    if not os.path.exists(tif_path):
        print(f"警告: {tif_path} 不存在，跳过")
        continue

    try:
        with rasterio.open(tif_path) as src:
            # 裁剪到研究区
            out_image, out_transform = mask(
                src,
                geometries,
                crop=True,
                nodata=np.nan  # 设置NoData值
            )

            # 计算非空像素的平均值
            mean_value = np.nanmean(out_image)
            yearly_gpp.append(mean_value)
            years_processed.append(year)
            print(f"年份 {year}: GPP 平均值 = {mean_value:.4f}")

            # 保存裁剪后的tif
            profile = src.profile
            profile.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            output_path = os.path.join(output_dir, f"GPP_{year}_clipped.tif")
            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(out_image)

    except Exception as e:
        print(f"处理 {year} 年数据时出错: {str(e)}")
        continue

# 检查是否有有效数据
if len(yearly_gpp) == 0:
    print("错误: 没有成功处理任何数据!")
    exit()

# 3. 绘制年际变化图
plt.figure(figsize=(12, 6))
plt.plot(years_processed, yearly_gpp, "o-", linewidth=2, markersize=8, color="#2ca25f")
plt.title("GPP年际变化 (2001-2021)", fontsize=14)
plt.xlabel("年份", fontsize=12)
plt.ylabel("GPP平均值 (gC/m2/yr)", fontsize=12)
plt.grid(alpha=0.3)

# 设置X轴刻度
if len(years_processed) > 0:
    # 确保年份范围正确
    min_year = min(years_processed)
    max_year = max(years_processed)
    # 每2年一个刻度
    plt.xticks(range(min_year, max_year + 1, 2))

# 标记极值点
if len(yearly_gpp) > 1:
    max_idx = np.argmax(yearly_gpp)
    min_idx = np.argmin(yearly_gpp)
    # 计算标注位置偏移量（基于数据范围）
    data_range = max(yearly_gpp) - min(yearly_gpp)
    offset = data_range * 0.15  # 偏移量为数据范围的15%

    plt.annotate(f"峰值: {yearly_gpp[max_idx]:.2f} ({years_processed[max_idx]})",
                 xy=(years_processed[max_idx], yearly_gpp[max_idx]),
                 xytext=(years_processed[max_idx], yearly_gpp[max_idx] + offset),
                 arrowprops=dict(arrowstyle="->", color="red"),
                 fontsize=10)
    plt.annotate(f"谷值: {yearly_gpp[min_idx]:.2f} ({years_processed[min_idx]})",
                 xy=(years_processed[min_idx], yearly_gpp[min_idx]),
                 xytext=(years_processed[min_idx], yearly_gpp[min_idx] - offset),
                 arrowprops=dict(arrowstyle="->", color="blue"),
                 fontsize=10)

# 添加趋势线
if len(yearly_gpp) > 1:
    # 线性回归
    z = np.polyfit(years_processed, yearly_gpp, 1)
    p = np.poly1d(z)
    plt.plot(years_processed, p(years_processed), "r--", label=f"趋势线 (斜率={z[0]:.4f})")
    plt.legend()

# 保存和显示
output_plot = os.path.join(output_dir, "GPP_trend.png")
plt.tight_layout()
plt.savefig(output_plot, dpi=300)
print(f"图表已保存至: {output_plot}")
plt.show()

# 4. 输出统计结果
print("\n碳汇变化分析结果:")
if len(yearly_gpp) > 1:
    print(f"• 处理年份: {min(years_processed)}-{max(years_processed)} (共{len(years_processed)}年)")
    # 判断趋势方向
    trend_direction = "上升" if z[0] > 0 else ("下降" if z[0] < 0 else "稳定")
    print(f"• 整体趋势: {trend_direction} (斜率={z[0]:.4f})")
    print(f"• 峰值年份: {years_processed[max_idx]}年 (GPP={yearly_gpp[max_idx]:.2f})")
    print(f"• 谷值年份: {years_processed[min_idx]}年 (GPP={yearly_gpp[min_idx]:.2f})")
    print(f"• 变化幅度: {max(yearly_gpp) - min(yearly_gpp):.2f} gC/m²/yr")
    print(f"• 平均值: {np.mean(yearly_gpp):.2f} ± {np.std(yearly_gpp):.2f} gC/m²/yr")
else:
    print(f"• 仅处理了{len(years_processed)}年数据，无法计算趋势")

# 5. 保存统计结果到CSV
csv_path = os.path.join(output_dir, "GPP_statistics.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("年份,GPP平均值\n")
    for year, value in zip(years_processed, yearly_gpp):
        f.write(f"{year},{value}\n")
print(f"统计数据已保存至: {csv_path}")