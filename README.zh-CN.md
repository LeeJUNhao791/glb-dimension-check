# GLB 尺寸验收

[English](README.md) · [在线试用](https://leejunhao791.github.io/glb-dimension-check/)

按毫米读取静态 GLB 的场景包围盒，并逐轴对照图纸或交付尺寸。可在 Web 3D 或 AR 交付前发现导出单位和轴顺序错误。

## 浏览器快速体验

1. 打开在线示例，点击 **Pass example** 和 **1000× scale error**。两个样例共用 `120 × 80 × 40 mm` 的参考尺寸和每轴 `0.1 mm` 的容差，结果分别为 PASS 和 FAIL。
2. 检查自己的模型时，拖入一个 `.glb` 文件，按场景的 X、Y、Z 轴输入预期尺寸和容差，再点击 **Check dimensions**。
3. PASS 和 FAIL 均可下载。点击 **Download SVG** 保存验收卡，或点击 **Download JSON** 保存与命令行输出一致的检查报告。

网页使用 Pyodide 在浏览器内运行 Python 检查器。首次检查会从 jsDelivr 加载运行时，你选择的 GLB 文件留在浏览器中。纯离线检查可使用下面的命令行。

## 命令行与离线检查

在仓库根目录运行，使用 Python 3.8 或更新版本，无须安装第三方库。

```sh
python scripts/check_glb.py examples/correct.glb --expected-mm 120 80 40
python scripts/check_glb.py examples/1000x-too-large.glb --expect examples/expected.json --svg scale-error.svg
python scripts/check_glb.py examples/measure-only.glb
```

第一条命令通过并返回 `0`。第二条命令报告 1000 倍的尺寸错误并返回 `1`，同时生成 `scale-error.svg`。第三条命令只测量尺寸并返回 `0`。输入或写入错误返回 `2`。

可复制 [JSON 预期尺寸模板](examples/expected.json)，按模型调整 `expected_mm` 和 `tolerance_mm`。默认容差为每轴 `0.1 mm`。`--expect` 和 `--expected-mm`／`--tolerance-mm` 分开使用。更多参数见 [英文文档](README.md#check-against-a-json-expectation-file)。

## 检查自己的模型

先测量 GLB，再把图纸尺寸映射到 GLB 的 X、Y、Z 轴。导出时的坐标转换会影响轴顺序，模型旋转也会改变沿三轴测得的包围盒。Hammond 1590B 外壳以 `112.4 × 60.5 × 31.0 mm`（GLB X/Y/Z）进行检查。

[Hammond 原厂图纸](https://www.hammfg.com/files/parts/pdf/1590B.pdf) · [正常导出 PASS](examples/hammond-1590b-pass.svg) · [1000 倍比例 FAIL](examples/hammond-1590b-1000x-fail.svg)

支持使用单个内嵌二进制缓冲区和标准 float32 顶点的静态 GLB 2.0。动画、蒙皮、变形目标以及压缩或量化几何超出当前范围。使用 STEP、FBX、OBJ、STL 或分离式 `.gltf` 时，先导出静态 GLB，再核对轴顺序和导出单位。

[MIT 许可证](LICENSE)
