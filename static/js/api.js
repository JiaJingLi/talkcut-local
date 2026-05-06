const API = {
    // ========== 分析 ==========
    async analyze(videoFile) {
        const formData = new FormData();
        formData.append('video', videoFile);

        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '分析失败');
        }

        return response.json();
    },

    // ========== 获取项目数据 ==========
    async getProject(projectId) {
        const response = await fetch(`/api/project/${projectId}/json`);
        if (!response.ok) {
            throw new Error('加载项目失败');
        }
        return response.json();
    },

    // ========== 获取视频流地址 ==========
    getVideoStream(projectId) {
        return `/api/project/${projectId}/stream`;
    },

    // ========== 渲染 ==========
    async render(projectId, timeline) {
        const response = await fetch(`/api/project/${projectId}/render`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ timeline })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '渲染失败');
        }

        return response.json();
    },

    // ========== 下载 ==========
    download(projectId) {
        return `/api/project/${projectId}/download`;
    },

    // ========== 配置管理 ==========

    /**
     * 获取当前配置
     * @returns {Promise<Object>} 配置对象
     */
    async getConfig() {
        const response = await fetch('/api/config');
        if (!response.ok) {
            throw new Error('获取配置失败');
        }
        return response.json();
    },

    /**
     * 更新配置
     * @param {Object} data - 配置数据，可包含 filler_words, filler_ratio_threshold 等
     * @returns {Promise<Object>}
     */
    async updateConfig(data) {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '更新配置失败');
        }

        return response.json();
    },

    /**
     * 用当前最新配置重新分析已有项目
     * @param {string} projectId
     * @returns {Promise<Object>} 新的分析结果
     */
    async reanalyze(projectId) {
        const response = await fetch(`/api/project/${projectId}/reanalyze`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '重新分析失败');
        }

        return response.json();
    }
};
