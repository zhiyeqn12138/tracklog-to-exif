"""
UI页面模块
使用NiceGUI构建Web界面
"""
from nicegui import ui, run
from pathlib import Path
import asyncio
import os
from typing import Optional
from .state import app_state
from core.scan import scan_photos
from core.match import match_photos_to_track
from core.pipeline import process_pipeline


def setup_ui():
    """设置UI界面"""
    
    # 自动保存配置的函数
    def auto_save_config():
        """自动保存配置到文件"""
        app_state.save_to_config()
    
    # 页面样式
    ui.add_head_html('''
    <style>
        .custom-card {
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-card {
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
        }
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }
    </style>
    ''')
    
    # 标题区域
    with ui.header().classes('items-center justify-between'):
        ui.label('📍 tracklog-to-exif').classes('text-h4')
        with ui.row().classes('gap-2 items-center'):
            ui.badge('配置自动保存', color='green').classes('text-xs').tooltip('参数修改后自动保存到config.json')
            ui.label('v1.0').classes('text-caption')
    
    # 主容器
    with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
        
        # 使用说明
        with ui.expansion('📖 使用说明', icon='help_outline').classes('w-full'):
            ui.markdown('''
            **功能说明**：根据照片拍摄时间和GPS轨迹数据，为照片添加地理位置信息。
            
            **使用步骤**：
            1. 选择照片文件夹和轨迹文件（GPX或CSV格式）
            2. 设置参数（时区、时间偏移、匹配模式等）
            3. 点击"扫描照片"查看照片分类情况
            4. 点击"匹配预览"查看匹配结果
            5. 设置输出目录，点击"开始处理"写入GPS信息
            6. 查看处理报告
            
            **注意事项**：
            - 支持JPG/JPEG格式照片
            - 支持GPX和CSV两种轨迹格式
            - 照片需要有拍摄时间（EXIF信息）
            - 处理过程会创建副本，不会修改原始照片
            ''')
        
        # ==================== 文件选择区域 ====================
        with ui.card().classes('w-full custom-card'):
            ui.label('📁 文件选择').classes('text-h6')
            
            with ui.row().classes('w-full gap-4'):
                # 照片文件夹
                with ui.column().classes('flex-1'):
                    ui.label('照片文件夹：').classes('font-bold')
                    with ui.row().classes('w-full gap-2'):
                        folder_input = ui.input(
                            label='文件夹路径',
                            placeholder='请输入或选择照片文件夹路径',
                            value=app_state.folder_path
                        ).classes('flex-1')
                        folder_input.bind_value(app_state, 'folder_path')
                        folder_input.on('blur', lambda: auto_save_config())
                        
                        def show_folder_help():
                            ui.notify('请在输入框中手动输入照片文件夹路径', type='info', position='top')
                        
                        ui.button(icon='folder_open', on_click=show_folder_help).props('flat').tooltip('输入文件夹路径')
                    
                    with ui.row():
                        recursive_switch = ui.checkbox('递归扫描子文件夹', value=app_state.recursive)
                        recursive_switch.bind_value(app_state, 'recursive')
                        recursive_switch.on_value_change(lambda: auto_save_config())
                
                # 轨迹文件
                with ui.column().classes('flex-1'):
                    ui.label('轨迹文件：').classes('font-bold')
                    with ui.row().classes('w-full gap-2'):
                        track_input = ui.input(
                            label='轨迹文件路径',
                            placeholder='请输入或选择GPX/CSV文件路径',
                            value=app_state.track_path
                        ).classes('flex-1')
                        track_input.bind_value(app_state, 'track_path')
                        track_input.on('blur', lambda: auto_save_config())
                        
                        def show_track_help():
                            ui.notify('请在输入框中手动输入轨迹文件路径（包含文件名）', type='info', position='top')
                        
                        ui.button(icon='upload_file', on_click=show_track_help).props('flat').tooltip('输入文件路径')
                    
                    track_type_select = ui.select(
                        label='轨迹文件类型',
                        options=['gpx', 'csv'],
                        value=app_state.track_type
                    ).classes('w-full')
                    track_type_select.bind_value(app_state, 'track_type')
        
        # ==================== 参数设置区域 ====================
        with ui.card().classes('w-full custom-card'):
            ui.label('⚙️ 参数设置').classes('text-h6')
            
            with ui.row().classes('w-full gap-4'):
                # 左列
                with ui.column().classes('flex-1'):
                    photo_tz_input = ui.number(
                        label='照片时区偏移（小时）',
                        value=app_state.photo_tz_offset,
                        step=0.5,
                        min=-12,
                        max=14
                    ).classes('w-full')
                    photo_tz_input.bind_value(app_state, 'photo_tz_offset')
                    photo_tz_input.on('blur', lambda: auto_save_config())
                    
                    camera_offset_input = ui.number(
                        label='相机时间偏移（秒）',
                        value=app_state.camera_offset_sec,
                        step=1
                    ).classes('w-full')
                    camera_offset_input.bind_value(app_state, 'camera_offset_sec')
                    camera_offset_input.on('blur', lambda: auto_save_config())
                
                # 右列
                with ui.column().classes('flex-1'):
                    max_error_input = ui.number(
                        label='最大时间误差阈值（秒）',
                        value=app_state.max_error_sec,
                        step=10,
                        min=10
                    ).classes('w-full')
                    max_error_input.bind_value(app_state, 'max_error_sec')
                    max_error_input.on('blur', lambda: auto_save_config())
                    
                    match_method_select = ui.select(
                        label='匹配模式',
                        options={
                            'nearest': '最近点（速度快）',
                            'interp': '线性插值（精度高）'
                        },
                        value=app_state.match_method
                    ).classes('w-full')
                    match_method_select.bind_value(app_state, 'match_method')
                    match_method_select.on_value_change(lambda: auto_save_config())
            
            # 距离过滤（仅插值模式）
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                distance_filter_switch = ui.checkbox('启用距离过滤（插值模式）', value=app_state.max_distance_m is not None)
                
                distance_input = ui.number(
                    label='最大距离（米）',
                    value=app_state.max_distance_m or 10000.0,
                    step=100.0,
                    min=1.0
                ).classes('w-40')
                
                def update_distance_filter():
                    if distance_filter_switch.value:
                        app_state.max_distance_m = distance_input.value
                    else:
                        app_state.max_distance_m = None
                    auto_save_config()
                
                distance_filter_switch.on_value_change(lambda: update_distance_filter())
                distance_input.on('blur', lambda: update_distance_filter())
                distance_input.bind_enabled_from(distance_filter_switch, 'value')
            
            with ui.row().classes('w-full'):
                ui.label('提示：启用后，两个轨迹点间距离超过设定值时，将降级为最近点模式').classes('text-xs text-gray-600')
            
            # CSV专用参数（动态显示）
            csv_params_container = ui.column().classes('w-full')
            
            def update_csv_params_visibility():
                csv_params_container.clear()
                if app_state.track_type == 'csv':
                    with csv_params_container:
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.label('CSV列映射').classes('text-sm font-bold')
                            ui.badge('当前: 一生足迹格式', color='green').classes('text-xs')
                            
                            def set_standard_format():
                                ui.notify('已切换到标准格式', type='info')
                                app_state.csv_col_map['time'] = 'time'
                                app_state.csv_col_map['lat'] = 'lat'
                                app_state.csv_col_map['lon'] = 'lon'
                                auto_save_config()
                                update_csv_params_visibility()
                            
                            def set_yishengzuji_format():
                                ui.notify('已切换到"一生足迹"格式', type='info')
                                app_state.csv_col_map['time'] = 'dataTime'
                                app_state.csv_col_map['lat'] = 'latitude'
                                app_state.csv_col_map['lon'] = 'longitude'
                                auto_save_config()
                                update_csv_params_visibility()
                            
                            ui.button('标准格式', icon='description', on_click=set_standard_format).props('flat dense').classes('text-xs')
                            ui.button('一生足迹', icon='location_on', on_click=set_yishengzuji_format).props('flat dense').classes('text-xs')
                        
                        with ui.row().classes('w-full gap-4'):
                            csv_time_col = ui.input(
                                label='时间列名',
                                value=app_state.csv_col_map.get('time', 'dataTime')
                            ).classes('flex-1')
                            csv_time_col.bind_value(app_state.csv_col_map, 'time')
                            csv_time_col.on('blur', lambda: auto_save_config())
                            
                            csv_lat_col = ui.input(
                                label='纬度列名',
                                value=app_state.csv_col_map.get('lat', 'latitude')
                            ).classes('flex-1')
                            csv_lat_col.bind_value(app_state.csv_col_map, 'lat')
                            csv_lat_col.on('blur', lambda: auto_save_config())
                            
                            csv_lon_col = ui.input(
                                label='经度列名',
                                value=app_state.csv_col_map.get('lon', 'longitude')
                            ).classes('flex-1')
                            csv_lon_col.bind_value(app_state.csv_col_map, 'lon')
                            csv_lon_col.on('blur', lambda: auto_save_config())
            
            def on_track_type_change():
                auto_save_config()
                update_csv_params_visibility()
            
            track_type_select.on_value_change(lambda: on_track_type_change())
            update_csv_params_visibility()
        
        # ==================== 扫描结果区域 ====================
        with ui.card().classes('w-full custom-card'):
            ui.label('🔍 扫描结果').classes('text-h6')
            
            # 扫描按钮
            scan_button = ui.button('扫描照片', icon='search', color='primary')
            scan_button.classes('mt-2')
            
            # 统计卡片容器
            scan_stats_container = ui.row().classes('w-full gap-4 mt-4')
            
            # 照片列表容器
            scan_table_container = ui.column().classes('w-full mt-4')
            
            async def do_scan():
                """执行扫描"""
                scan_button.props('loading')
                scan_button.disable()
                
                try:
                    # 验证输入
                    if not app_state.folder_path:
                        ui.notify('请选择照片文件夹', type='warning')
                        return
                    
                    if not Path(app_state.folder_path).exists():
                        ui.notify('照片文件夹不存在', type='negative')
                        return
                    
                    # 执行扫描
                    already_gps, need_process, no_time = await run.io_bound(
                        scan_photos,
                        app_state.folder_path,
                        app_state.recursive
                    )
                    
                    # 更新状态
                    app_state.already_gps = already_gps
                    app_state.need_process = need_process
                    app_state.no_time = no_time
                    
                    # 显示统计
                    summary = app_state.get_scan_summary()
                    scan_stats_container.clear()
                    with scan_stats_container:
                        # 总照片数
                        with ui.card().classes('flex-1 stat-card'):
                            ui.label(str(summary['total'])).classes('stat-number')
                            ui.label('总照片数').classes('stat-label')
                        
                        # 已有GPS
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'):
                            ui.label(str(summary['already_gps'])).classes('stat-number')
                            ui.label('已有GPS').classes('stat-label')
                        
                        # 待处理
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'):
                            ui.label(str(summary['need_process'])).classes('stat-number')
                            ui.label('待处理').classes('stat-label')
                        
                        # 无时间
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'):
                            ui.label(str(summary['no_time'])).classes('stat-number')
                            ui.label('无时间').classes('stat-label')
                    
                    # 显示照片列表
                    scan_table_container.clear()
                    with scan_table_container:
                        if summary['total'] > 0:
                            # 创建表格数据
                            rows = []
                            for photo in already_gps:
                                rows.append({
                                    'filename': Path(photo.path).name,
                                    'datetime': photo.datetime_utc.strftime('%Y-%m-%d %H:%M:%S') if photo.datetime_utc else '',
                                    'status': '已有GPS',
                                    'status_color': 'green'
                                })
                            for photo in need_process:
                                rows.append({
                                    'filename': Path(photo.path).name,
                                    'datetime': photo.datetime_utc.strftime('%Y-%m-%d %H:%M:%S') if photo.datetime_utc else '',
                                    'status': '待处理',
                                    'status_color': 'orange'
                                })
                            for photo in no_time:
                                rows.append({
                                    'filename': Path(photo.path).name,
                                    'datetime': '无时间',
                                    'status': '无时间',
                                    'status_color': 'gray'
                                })
                            
                            ui.table(
                                columns=[
                                    {'name': 'filename', 'label': '文件名', 'field': 'filename', 'align': 'left'},
                                    {'name': 'datetime', 'label': '拍摄时间（UTC）', 'field': 'datetime', 'align': 'left'},
                                    {'name': 'status', 'label': '状态', 'field': 'status', 'align': 'center'}
                                ],
                                rows=rows,
                                row_key='filename',
                                pagination={'rowsPerPage': 10, 'sortBy': 'filename'}
                            ).classes('w-full')
                    
                    ui.notify(f'扫描完成：共 {summary["total"]} 张照片', type='positive')
                
                except Exception as e:
                    ui.notify(f'扫描失败：{str(e)}', type='negative')
                
                finally:
                    scan_button.props(remove='loading')
                    scan_button.enable()
            
            scan_button.on_click(do_scan)
        
        # ==================== 匹配预览区域 ====================
        with ui.card().classes('w-full custom-card'):
            ui.label('🎯 匹配预览').classes('text-h6')
            
            # 匹配按钮
            match_button = ui.button('匹配预览', icon='location_on', color='secondary')
            match_button.classes('mt-2')
            
            # 匹配统计容器
            match_stats_container = ui.row().classes('w-full gap-4 mt-4')
            
            # 匹配结果表格容器
            match_table_container = ui.column().classes('w-full mt-4')
            
            async def do_match():
                """执行匹配预览"""
                match_button.props('loading')
                match_button.disable()
                
                try:
                    # 验证输入
                    if not app_state.need_process:
                        ui.notify('没有可处理的照片，如果未进行照片扫描，请先扫描照片', type='warning')
                        return
                    
                    if not app_state.track_path:
                        ui.notify('请选择轨迹文件', type='warning')
                        return
                    
                    if not Path(app_state.track_path).exists():
                        ui.notify('轨迹文件不存在', type='negative')
                        return
                    
                    # 解析轨迹
                    ui.notify('正在解析轨迹文件...', type='info')
                    
                    if app_state.track_type == 'gpx':
                        from core.track import parse_gpx
                        track_points = await run.io_bound(
                            parse_gpx,
                            app_state.track_path
                        )
                    else:  # csv
                        from core.track import parse_csv
                        track_points = await run.io_bound(
                            parse_csv,
                            app_state.track_path,
                            app_state.csv_col_map,
                            app_state.csv_time_is_utc,
                            app_state.csv_tz_offset
                        )
                    
                    ui.notify(f'轨迹解析完成：共 {len(track_points)} 个轨迹点', type='info')
                    
                    # 执行匹配
                    match_results = await run.io_bound(
                        match_photos_to_track,
                        app_state.need_process,
                        track_points,
                        app_state.photo_tz_offset,
                        app_state.camera_offset_sec,
                        app_state.max_error_sec,
                        app_state.match_method
                    )
                    
                    # 更新状态
                    app_state.match_results = match_results
                    
                    # 显示统计
                    summary = app_state.get_match_summary()
                    match_stats_container.clear()
                    with match_stats_container:
                        # 总数
                        with ui.card().classes('flex-1 stat-card'):
                            ui.label(str(summary['total'])).classes('stat-number')
                            ui.label('待匹配照片').classes('stat-label')
                        
                        # 匹配成功
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'):
                            ui.label(str(summary['matched'])).classes('stat-number')
                            ui.label('匹配成功').classes('stat-label')
                        
                        # 匹配失败
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'):
                            ui.label(str(summary['unmatched'])).classes('stat-number')
                            ui.label('匹配失败').classes('stat-label')
                        
                        # 超阈值
                        with ui.card().classes('flex-1 stat-card').style('background: linear-gradient(135deg, #fa709a 0%, #fee140 100%)'):
                            ui.label(str(summary['too_far'])).classes('stat-number')
                            ui.label('超阈值').classes('stat-label')
                    
                    # 显示匹配结果表格
                    match_table_container.clear()
                    with match_table_container:
                        if match_results:
                            rows = []
                            for match in match_results:
                                photo_name = Path(match.photo_path).name
                                photo = next((p for p in app_state.need_process if p.path == match.photo_path), None)
                                rows.append({
                                    'filename': photo_name,
                                    'datetime': photo.datetime_utc.strftime('%Y-%m-%d %H:%M:%S') if photo and photo.datetime_utc else '',
                                    'status': '✓ 匹配成功' if match.status == 'matched' else '✗ 匹配失败',
                                    'error_sec': f'{match.error_sec:.1f}' if match.error_sec is not None else '',
                                    'lat': f'{match.lat:.6f}' if match.lat is not None else '',
                                    'lon': f'{match.lon:.6f}' if match.lon is not None else '',
                                    'reason': match.reason or ''
                                })
                            
                            ui.table(
                                columns=[
                                    {'name': 'filename', 'label': '文件名', 'field': 'filename', 'align': 'left'},
                                    {'name': 'datetime', 'label': '拍摄时间（UTC）', 'field': 'datetime', 'align': 'left'},
                                    {'name': 'status', 'label': '状态', 'field': 'status', 'align': 'center'},
                                    {'name': 'error_sec', 'label': '误差（秒）', 'field': 'error_sec', 'align': 'right'},
                                    {'name': 'lat', 'label': '纬度', 'field': 'lat', 'align': 'right'},
                                    {'name': 'lon', 'label': '经度', 'field': 'lon', 'align': 'right'},
                                    {'name': 'reason', 'label': '说明', 'field': 'reason', 'align': 'left'}
                                ],
                                rows=rows,
                                row_key='filename',
                                pagination={'rowsPerPage': 10}
                            ).classes('w-full')
                    
                    ui.notify(f'匹配完成：{summary["matched"]}/{summary["total"]} 张照片匹配成功', type='positive')
                
                except Exception as e:
                    ui.notify(f'匹配失败：{str(e)}', type='negative')
                
                finally:
                    match_button.props(remove='loading')
                    match_button.enable()
            
            match_button.on_click(do_match)
        
        # ==================== 写入输出区域 ====================
        with ui.card().classes('w-full custom-card'):
            ui.label('💾 写入输出').classes('text-h6')
            
            # 输出模式选择
            with ui.row().classes('w-full gap-4 items-center'):
                ui.label('输出模式：').classes('font-bold')
                output_mode_group = ui.radio(
                    options={
                        'copy': '📋 创建副本到新目录（安全，推荐）',
                        'overwrite': '⚠️ 直接覆盖原照片（谨慎使用）'
                    },
                    value=app_state.output_mode
                ).props('inline')
                output_mode_group.bind_value(app_state, 'output_mode')
            
            # 输出目录（仅在copy模式下显示）
            output_dir_container = ui.column().classes('w-full')
            
            def update_output_dir_visibility():
                output_dir_container.clear()
                if app_state.output_mode == 'copy':
                    with output_dir_container:
                        with ui.row().classes('w-full gap-2'):
                            output_dir_input = ui.input(
                                label='输出目录',
                                value=app_state.output_dir,
                                placeholder='处理后的照片保存目录'
                            ).classes('flex-1')
                            output_dir_input.bind_value(app_state, 'output_dir')
                            output_dir_input.on('blur', lambda: auto_save_config())
                            
                            def show_output_help():
                                ui.notify('请在输入框中手动输入输出目录路径', type='info', position='top')
                            
                            ui.button(icon='folder_open', on_click=show_output_help).props('flat').tooltip('输入目录路径')
                else:
                    with output_dir_container:
                        ui.label('⚠️ 注意：将直接修改原照片文件，请确保已备份！').classes('text-orange font-bold')
            
            def on_output_mode_change():
                auto_save_config()
                update_output_dir_visibility()
            
            output_mode_group.on_value_change(lambda: on_output_mode_change())
            update_output_dir_visibility()
            
            # 报告生成开关
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                report_switch = ui.checkbox('生成处理报告（CSV格式）', value=app_state.generate_report)
                report_switch.bind_value(app_state, 'generate_report')
                report_switch.on_value_change(lambda: auto_save_config())
                ui.label('报告包含所有照片的处理状态、匹配结果等详细信息').classes('text-sm text-gray-600')
            
            # 开始处理按钮
            process_button = ui.button('开始处理', icon='play_arrow', color='positive')
            process_button.classes('mt-2')
            
            # 进度显示容器
            progress_container = ui.column().classes('w-full mt-4')
            
            # 结果显示容器
            result_container = ui.column().classes('w-full mt-4')
            
            async def do_process():
                """执行完整处理流程"""
                process_button.props('loading')
                process_button.disable()
                
                # 清空进度和结果容器
                progress_container.clear()
                result_container.clear()
                
                try:
                    # 验证输入
                    if not app_state.folder_path or not Path(app_state.folder_path).exists():
                        ui.notify('请选择有效的照片文件夹', type='negative')
                        return
                    
                    if not app_state.track_path or not Path(app_state.track_path).exists():
                        ui.notify('请选择有效的轨迹文件', type='negative')
                        return
                    
                    # 创建进度显示
                    with progress_container:
                        progress_label = ui.label('准备开始处理...').classes('text-sm')
                        progress_bar = ui.linear_progress(value=0, show_value=False).classes('w-full')
                    
                    # 进度回调
                    def on_progress(phase: str, done: int, total: int, message: str):
                        app_state.task_phase = phase
                        app_state.task_progress = done / total if total > 0 else 0
                        app_state.task_message = message
                        
                        # 更新UI
                        phase_names = {
                            'scanning': '📷 扫描照片',
                            'parsing_track': '🗺️ 解析轨迹',
                            'matching': '🎯 匹配坐标',
                            'writing': '💾 写入GPS',
                            'reporting': '📊 生成报告'
                        }
                        phase_name = phase_names.get(phase, phase)
                        progress_label.text = f'{phase_name}: {message}'
                        progress_bar.value = app_state.task_progress
                    
                    # 执行流水线
                    summary = await run.io_bound(
                        process_pipeline,
                        app_state.folder_path,
                        app_state.track_path,
                        app_state.track_type,
                        app_state.output_dir,
                        app_state.output_mode,
                        app_state.generate_report,
                        app_state.recursive,
                        app_state.photo_tz_offset,
                        app_state.camera_offset_sec,
                        app_state.max_error_sec,
                        app_state.match_method,
                        app_state.max_distance_m,
                        app_state.csv_col_map if app_state.track_type == 'csv' else None,
                        app_state.csv_time_is_utc if app_state.track_type == 'csv' else True,
                        app_state.csv_tz_offset if app_state.track_type == 'csv' else 0.0,
                        on_progress
                    )
                    
                    # 显示结果
                    result_container.clear()
                    with result_container:
                        ui.label('✅ 处理完成！').classes('text-h6 text-green')
                        
                        # 统计信息
                        with ui.row().classes('w-full gap-4 mt-2'):
                            with ui.card().classes('flex-1'):
                                ui.label('总照片数').classes('text-sm text-gray-600')
                                ui.label(str(summary['total'])).classes('text-2xl font-bold')
                            
                            with ui.card().classes('flex-1'):
                                ui.label('匹配成功').classes('text-sm text-gray-600')
                                ui.label(str(summary['matched'])).classes('text-2xl font-bold text-green')
                            
                            with ui.card().classes('flex-1'):
                                ui.label('写入成功').classes('text-sm text-gray-600')
                                ui.label(str(summary['write_success'])).classes('text-2xl font-bold text-blue')
                            
                            with ui.card().classes('flex-1'):
                                ui.label('写入失败').classes('text-sm text-gray-600')
                                ui.label(str(summary['write_failed'])).classes('text-2xl font-bold text-red')
                        
                        # 输出路径信息
                        ui.separator()
                        ui.label(f"📁 输出目录：{summary['output_dir']}").classes('text-sm')
                        if summary.get('report_path'):
                            ui.label(f"📊 报告文件：{summary['report_path']}").classes('text-sm')
                        else:
                            ui.label("📊 已跳过报告生成").classes('text-sm text-gray-600')
                        
                        # 打开文件夹按钮
                        def open_output_folder():
                            import subprocess
                            import platform
                            output_path = Path(summary['output_dir']).absolute()
                            if platform.system() == 'Windows':
                                os.startfile(output_path)
                            elif platform.system() == 'Darwin':  # macOS
                                subprocess.run(['open', output_path])
                            else:  # Linux
                                subprocess.run(['xdg-open', output_path])
                        
                        ui.button('打开输出文件夹', icon='folder_open', on_click=open_output_folder).classes('mt-2')
                    
                    ui.notify('处理完成！', type='positive')
                
                except Exception as e:
                    result_container.clear()
                    with result_container:
                        ui.label('❌ 处理失败').classes('text-h6 text-red')
                        ui.label(str(e)).classes('text-sm text-red')
                    ui.notify(f'处理失败：{str(e)}', type='negative')
                
                finally:
                    process_button.props(remove='loading')
                    process_button.enable()
            
            process_button.on_click(do_process)
        
        # 页脚
        ui.separator()
        with ui.row().classes('w-full justify-center'):
            ui.label('tracklog-to-exif | 照片exif的GPS标注 | 支持GPX和CSV轨迹格式 | by zhiyeqn').classes('text-sm text-gray-600')

