#!/usr/bin/env python3
"""
批量图片OCR导入脚本
用于批量处理财报图片并导入数据库
"""

import sys
from pathlib import Path
from utils.batch_image_processor import BatchImageProcessor


def main():
    if len(sys.argv) < 3:
        print("用法: python batch_import_images.py <图片目录> <资产ID>")
        print("示例: python batch_import_images.py ./财报截图 CN:STOCK:600036")
        print("\n支持的图片格式: .png, .jpg, .jpeg")
        return
    
    image_dir = Path(sys.argv[1])
    asset_id = sys.argv[2]
    
    if not image_dir.exists():
        print(f"错误: 目录不存在 {image_dir}")
        return
    
    # 支持的图片格式
    image_extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG']
    image_files = []
    for ext in image_extensions:
        image_files.extend(list(image_dir.glob(f'*{ext}')))
    
    if not image_files:
        print(f"错误: 在 {image_dir} 中未找到图片文件")
        return
    
    print(f"找到 {len(image_files)} 个图片文件")
    print(f"目标资产: {asset_id}")
    print("-" * 50)
    
    processor = BatchImageProcessor()
    results = []
    
    for idx, image_file in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] 处理: {image_file.name}")
        
        # 模拟Streamlit UploadedFile
        class MockUploadedFile:
            def __init__(self, file_path):
                self.name = file_path.name
                self._path = file_path
            
            def getvalue(self):
                with open(self._path, 'rb') as f:
                    return f.read()
        
        mock_file = MockUploadedFile(image_file)
        
        result = processor.process_single_image(
            file=mock_file,
            asset_id=asset_id,
            data_source='IMAGE_OCR'
        )
        results.append(result)
        
        if result['status'] == 'success':
            confidence = result.get('confidence', 0)
            print(f"  ✓ 成功 ({result.get('report_date', 'N/A')}) [置信度: {confidence:.1%}]")
        else:
            print(f"  ✗ 失败: {result.get('error', '未知错误')}")
    
    print("-" * 50)
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"完成: {success_count}/{len(results)} 成功")
    
    # 显示详细结果
    if success_count > 0:
        print("\n成功导入的数据:")
        for result in results:
            if result['status'] == 'success':
                print(f"  - {result['file_name']}: {result['report_date']} ({result['metrics_count']} 个指标)")


if __name__ == "__main__":
    main()
