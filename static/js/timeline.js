class Timeline {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.duration = 0;
        this.segments = [];
        this.autoCuts = [];
        this.issues = [];
        this.keptRanges = [];
        this.currentTime = 0;
        this.isDragging = false;
        this.dragType = null;
        this.dragIndex = -1;
        this.waveformData = null;  // 波形数据

        this.options = {
            height: options.height || 200,
            waveHeight: 60,
            segmentHeight: 30,
            cutHeight: 20,
            issueHeight: 15,
            padding: 10,
            colors: {
                background: '#0f3460',
                waveform: '#1a4a7a',
                waveformLine: '#4a9aea',
                segment: '#27ae60',
                cut: '#e74c3c',
                kept: '#27ae60',
                removed: '#2c2c3a',
                playhead: '#e94560',
                text: '#fff',
                issue: '#f39c12',
                issueFlag: '#f39c12'
            },
            ...options
        };

        this.setupEvents();
    }

    setupEvents() {
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('mouseleave', () => this.onMouseUp());
    }

    /**
     * 设置波形数据（数组，每个元素为 0~1 的归一化幅度值）
     * @param {number[]} data
     */
    setWaveformData(data) {
        this.waveformData = data;
        this.draw();
    }

    setData(data) {
        this.segments = data.segments || [];
        this.autoCuts = data.auto_cuts || [];
        this.issues = data.issues || [];
        this.duration = data.duration || 0;

        this.calculateKeptRanges();
        this.draw();
    }

    /**
     * 移除指定时间区间的剪辑点（保留该段）
     * 核心逻辑：遍历所有剪辑点，逐个处理与 [start, end] 的重叠关系
     *
     * 五种情况：
     *  1. 完全不重叠 → 保留原样
     *  2. 目标完全在剪辑点内部 → 拆成两段 [cut.start, start] 和 [end, cut.end]
     *  3. 剪辑点左侧与目标重叠 → 保留右侧 [end, cut.end]
     *  4. 剪辑点右侧与目标重叠 → 保留左侧 [cut.start, start]
     *  5. 剪辑点完全被目标包含 → 完全删除
     *
     * @param {number} start
     * @param {number} end
     */
    removeCut(start, end) {
        const newCuts = [];

        for (const cut of this.autoCuts) {
            const cutStart = cut.start;
            const cutEnd = cut.end;

            // 情况1：完全不重叠（剪辑点在目标左侧或右侧）
            if (cutEnd <= start || cutStart >= end) {
                newCuts.push(cut);
                continue;
            }

            // 情况2：目标区间完全在剪辑点内部（剪辑点包围目标）
            // 需要拆成两段：保留剪辑点左侧和目标右侧
            if (cutStart < start && cutEnd > end) {
                // 左侧段（目标开始前）
                if (cutStart < start) {
                    newCuts.push({
                        start: cutStart,
                        end: start,
                        duration: start - cutStart,
                        reason: cut.reason || 'manual'
                    });
                }
                // 右侧段（目标结束后）
                if (end < cutEnd) {
                    newCuts.push({
                        start: end,
                        end: cutEnd,
                        duration: cutEnd - end,
                        reason: cut.reason || 'manual'
                    });
                }
                continue;
            }

            // 情况3：剪辑点与目标右侧重叠（剪辑点左侧超出目标开始）
            // 即：cutStart < end && cutEnd > end（剪辑点右端超出目标右端）
            if (cutEnd > end) {
                const newStart = Math.max(end, cutStart);
                if (newStart < cutEnd) {
                    newCuts.push({
                        start: newStart,
                        end: cutEnd,
                        duration: cutEnd - newStart,
                        reason: cut.reason || 'manual'
                    });
                }
            }

            // 情况4：剪辑点与目标左侧重叠（剪辑点右侧超出目标结束）
            // 即：cutEnd > start && cutStart < start（剪辑点左端超出目标左端）
            if (cutStart < start) {
                const newEnd = Math.min(start, cutEnd);
                if (cutStart < newEnd) {
                    newCuts.push({
                        start: cutStart,
                        end: newEnd,
                        duration: newEnd - cutStart,
                        reason: cut.reason || 'manual'
                    });
                }
            }

            // 情况5：剪辑点完全被目标区间包含 → 完全删除（不push）
            // 即：cutStart >= start && cutEnd <= end → 不做任何操作
        }

        this.autoCuts = newCuts;
        this._mergeOverlappingCuts();
        this.calculateKeptRanges();
        this.draw();
        this._emitChange();
    }

    /**
     * 直接保留指定区间（在 keptRanges 中强制加入该段）
     * 同时从 autoCuts 中移除与该段重叠的部分
     * @param {number} start
     * @param {number} end
     */
    keepRange(start, end) {
        // 1. 从 autoCuts 中移除所有与 [start, end] 重叠的剪辑点（拆分或删除）
        const newCuts = [];
        for (const cut of this.autoCuts) {
            if (cut.end <= start || cut.start >= end) {
                // 完全不重叠，保留
                newCuts.push(cut);
            } else if (cut.start >= start && cut.end <= end) {
                // 剪辑点完全被目标区间包含 → 完全删除（不保留）
            } else {
                // 部分重叠 → 保留不重叠的部分
                if (cut.start < start) {
                    newCuts.push({
                        start: cut.start,
                        end: start,
                        duration: start - cut.start,
                        reason: cut.reason || 'manual'
                    });
                }
                if (cut.end > end) {
                    newCuts.push({
                        start: end,
                        end: cut.end,
                        duration: cut.end - end,
                        reason: cut.reason || 'manual'
                    });
                }
            }
        }
        this.autoCuts = newCuts;
        this._mergeOverlappingCuts();
        this.calculateKeptRanges();
        this.draw();
        this._emitChange();
    }

    /**
     * 添加剪辑点（删除该段）
     * 如果该段位于保留区间内部，则将保留区间拆分
     * @param {number} start
     * @param {number} end
     * @param {string} reason - 'filler' 或 'silence'
     */
    addCut(start, end, reason = 'manual') {
        // 避免重复添加（检查是否有重叠的剪辑点）
        const hasOverlap = this.autoCuts.some(c =>
            !(c.end <= start || c.start >= end)
        );
        if (hasOverlap) return; // 已经有重叠的剪辑点，不重复添加

        // 添加新的剪辑点
        this.autoCuts.push({ start, end, duration: end - start, reason });

        // 合并重叠的剪辑点
        this._mergeOverlappingCuts();

        this.calculateKeptRanges();
        this.draw();
        this._emitChange();
    }

    /**
     * 合并重叠或相邻的剪辑点
     */
    _mergeOverlappingCuts() {
        if (this.autoCuts.length <= 1) return;

        // 按开始时间排序
        this.autoCuts.sort((a, b) => a.start - b.start);

        const merged = [this.autoCuts[0]];
        for (let i = 1; i < this.autoCuts.length; i++) {
            const current = this.autoCuts[i];
            const last = merged[merged.length - 1];

            // 如果当前剪辑点与上一个重叠或相邻（间隔<0.5秒）
            if (current.start <= last.end + 0.5) {
                // 合并：取最晚的结束时间
                last.end = Math.max(last.end, current.end);
                last.duration = last.end - last.start;
            } else {
                merged.push(current);
            }
        }

        this.autoCuts = merged;
    }

    /**
     * 保留全部（清除所有剪辑点）
     */
    keepAll() {
        this.autoCuts = [];
        this.calculateKeptRanges();
        this.draw();
        this._emitChange();
    }

    /**
     * 删除全部（将所有非问题区间都剪掉？实际上应该是恢复初始 autoCuts）
     * 这里实现为：将所有 issues 对应的区间加入 cuts
     */
    deleteAllCuts() {
        // 重新从 issues 生成剪辑点
        const newCuts = [];
        if (this.issues) {
            this.issues.forEach(issue => {
                newCuts.push({
                    start: issue.time,
                    end: issue.end,
                    duration: issue.end - issue.time,
                    reason: issue.type === 'filler_overuse' ? 'filler' : 'silence'
                });
            });
        }
        this.autoCuts = newCuts;
        this.calculateKeptRanges();
        this.draw();
        this._emitChange();
    }

    calculateKeptRanges() {
        if (this.duration === 0) {
            this.keptRanges = [];
            return;
        }

        // 如果没有剪辑点，保留整个视频
        if (this.autoCuts.length === 0) {
            this.keptRanges = [{ start: 0, end: this.duration }];
            return;
        }

        // 按开始时间排序剪辑点
        const sortedCuts = [...this.autoCuts].sort((a, b) => a.start - b.start);

        this.keptRanges = [];
        let currentStart = 0;

        for (const cut of sortedCuts) {
            if (cut.start > currentStart) {
                this.keptRanges.push({ start: currentStart, end: cut.start });
            }
            currentStart = Math.max(currentStart, cut.end);
        }

        if (currentStart < this.duration) {
            this.keptRanges.push({ start: currentStart, end: this.duration });
        }
    }

    _emitChange() {
        if (this.onChange) {
            this.onChange(this.keptRanges);
        }
    }

    getTimeFromX(x) {
        const rect = this.canvas.getBoundingClientRect();
        const canvasWidth = rect.width - this.options.padding * 2;
        const time = ((x - this.options.padding) / canvasWidth) * this.duration;
        return Math.max(0, Math.min(this.duration, time));
    }

    getXFromTime(time) {
        const rect = this.canvas.getBoundingClientRect();
        const canvasWidth = rect.width - this.options.padding * 2;
        return this.options.padding + (time / this.duration) * canvasWidth;
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const time = this.getTimeFromX(x);

        // 只在保留区间边缘检测拖拽
        for (let i = 0; i < this.keptRanges.length; i++) {
            const range = this.keptRanges[i];
            const x1 = this.getXFromTime(range.start);
            const x2 = this.getXFromTime(range.end);

            if (Math.abs(x - x1) < 10 || Math.abs(x - x2) < 10) {
                this.isDragging = true;
                this.dragType = Math.abs(x - x1) < Math.abs(x - x2) ? 'start' : 'end';
                this.dragIndex = i;
                return;
            }
        }
    }

    onMouseMove(e) {
        if (!this.isDragging) {
            // 显示悬停时间
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const time = this.getTimeFromX(x);
            this.canvas.style.cursor = 'default';

            for (const range of this.keptRanges) {
                const x1 = this.getXFromTime(range.start);
                const x2 = this.getXFromTime(range.end);
                if (Math.abs(e.clientX - rect.left - x1) < 10 || Math.abs(e.clientX - rect.left - x2) < 10) {
                    this.canvas.style.cursor = 'col-resize';
                    break;
                }
            }
            return;
        }

        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const time = this.getTimeFromX(x);

        const range = this.keptRanges[this.dragIndex];

        if (this.dragType === 'start') {
            range.start = Math.max(0, Math.min(time, range.end - 0.5));
        } else {
            range.end = Math.max(range.start + 0.5, Math.min(time, this.duration));
        }

        this.draw();

        if (this.onChange) {
            this.onChange(this.keptRanges);
        }
    }

    onMouseUp() {
        this.isDragging = false;
        this.dragType = null;
        this.dragIndex = -1;
    }

    setCurrentTime(time) {
        this.currentTime = time;
        this.draw();
    }

    draw() {
        const ctx = this.ctx;
        const canvas = this.canvas;
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.fillStyle = this.options.colors.background;
        ctx.fillRect(0, 0, width, height);

        if (this.duration === 0) return;

        const waveY = this.options.padding;
        const segY = waveY + this.options.waveHeight + 10;
        const cutY = segY + this.options.segmentHeight + 10;
        const issueY = cutY + this.options.cutHeight + 10;

        // ===== 绘制波形图 =====
        this._drawWaveform(ctx, width, waveY);

        // ===== 时间刻度 =====
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#888';
        ctx.font = '10px sans-serif';
        for (let i = 0; i <= 10; i++) {
            const x = this.options.padding + (width - this.options.padding * 2) * (i / 10);
            ctx.beginPath();
            ctx.moveTo(x, waveY);
            ctx.lineTo(x, waveY + this.options.waveHeight);
            ctx.stroke();

            const label = (this.duration * i / 10).toFixed(1) + 's';
            ctx.fillText(label, x - 15, waveY + this.options.waveHeight + 12);
        }

        // ===== 段落保留/删除状态 =====
        const totalWidth = width - this.options.padding * 2;

        // 先画全段为"删除"状态
        ctx.fillStyle = this.options.colors.removed;
        ctx.fillRect(this.options.padding, segY, totalWidth, this.options.segmentHeight);

        // 再覆盖"保留"区间
        for (const range of this.keptRanges) {
            const x1 = this.getXFromTime(range.start);
            const x2 = this.getXFromTime(range.end);
            ctx.fillStyle = this.options.colors.kept;
            ctx.fillRect(x1, segY, x2 - x1, this.options.segmentHeight);

            // 保留区间标签
            if (x2 - x1 > 30) {
                ctx.fillStyle = '#fff';
                ctx.font = '10px sans-serif';
                ctx.fillText(`${range.start.toFixed(1)}s`, x1 + 2, segY + 12);
            }
        }

        // ===== 剪辑点（auto_cuts）=====
        for (const cut of this.autoCuts) {
            const x1 = this.getXFromTime(cut.start);
            const x2 = this.getXFromTime(cut.end);
            ctx.fillStyle = this.options.colors.cut;
            ctx.fillRect(x1, cutY, x2 - x1, this.options.cutHeight);

            // 剪辑原因标签
            if (x2 - x1 > 40) {
                ctx.fillStyle = '#fff';
                ctx.font = '9px sans-serif';
                const label = cut.reason === 'filler' ? '语气词' : '静默';
                ctx.fillText(label, x1 + 2, cutY + 12);
            }
        }

        // ===== 问题标记（小旗标）=====
        for (const issue of this.issues) {
            const x = this.getXFromTime(issue.time);
            ctx.fillStyle = this.options.colors.issueFlag;
            ctx.beginPath();
            ctx.moveTo(x, issueY);
            ctx.lineTo(x + 6, issueY + this.options.issueHeight);
            ctx.lineTo(x - 6, issueY + this.options.issueHeight);
            ctx.closePath();
            ctx.fill();
        }

        // ===== 播放头 =====
        const playheadX = this.getXFromTime(this.currentTime);
        ctx.strokeStyle = this.options.colors.playhead;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(playheadX, waveY);
        ctx.lineTo(playheadX, height);
        ctx.stroke();

        // 播放头时间标签
        ctx.fillStyle = this.options.colors.playhead;
        ctx.fillRect(playheadX - 25, waveY - 16, 50, 14);
        ctx.fillStyle = '#fff';
        ctx.font = '10px sans-serif';
        ctx.fillText(this.currentTime.toFixed(2) + 's', playheadX - 20, waveY - 4);
    }

    /**
     * 绘制波形图
     */
    _drawWaveform(ctx, width, waveY) {
        const waveHeight = this.options.waveHeight;
        const centerY = waveY + waveHeight / 2;
        const waveWidth = width - this.options.padding * 2;

        // 背景
        ctx.fillStyle = this.options.colors.waveform;
        ctx.fillRect(this.options.padding, waveY, waveWidth, waveHeight);

        if (this.waveformData && this.waveformData.length > 0) {
            // 使用预计算的波形数据绘制
            const step = Math.max(1, Math.floor(this.waveformData.length / waveWidth));
            ctx.fillStyle = this.options.colors.waveformLine;

            for (let x = 0; x < waveWidth; x++) {
                const dataIndex = Math.floor((x / waveWidth) * this.waveformData.length);
                const amp = this.waveformData[dataIndex] || 0;
                const barHeight = amp * waveHeight;
                ctx.fillRect(
                    this.options.padding + x,
                    centerY - barHeight / 2,
                    1,
                    barHeight
                );
            }
        } else {
            // 没有波形数据时，画一条中心线
            ctx.strokeStyle = '#4a9aea';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(this.options.padding, centerY);
            ctx.lineTo(this.options.padding + waveWidth, centerY);
            ctx.stroke();

            // 提示文字
            ctx.fillStyle = '#666';
            ctx.font = '11px sans-serif';
            ctx.fillText('波形图（分析时将自动生成）', this.options.padding + 10, centerY + 4);
        }
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = this.options.height;
        this.draw();
    }

    getTimeline() {
        if (this.keptRanges.length === 0 && this.duration > 0) {
            return [[0, this.duration]];
        }
        return this.keptRanges.map(r => [r.start, r.end]);
    }

    setOnChange(callback) {
        this.onChange = callback;
    }
}
