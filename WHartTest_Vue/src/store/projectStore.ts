// src/store/projectStore.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getProjectList, type Project } from '@/services/projectService';

const PROJECT_STORAGE_KEY = 'selected_project_id';

export const useProjectStore = defineStore('project', () => {
  // 当前选中的项目
  const currentProject = ref<Project | null>(null);
  
  // 项目列表
  const projectList = ref<Project[]>([]);
  
  // 加载状态
  const loading = ref(false);
  
  // 错误信息
  const error = ref<string | null>(null);
  
  // 计算属性：当前项目ID
  const currentProjectId = computed(() => currentProject.value?.id || null);
  
  // 计算属性：项目选项列表（用于下拉选择器）
  const projectOptions = computed(() => {
    return projectList.value.map(project => ({
      label: project.name,
      value: project.id
    }));
  });

  // 从localStorage获取保存的项目ID
  const getSavedProjectId = (): number | null => {
    try {
      const savedId = localStorage.getItem(PROJECT_STORAGE_KEY);
      return savedId ? parseInt(savedId, 10) : null;
    } catch (error) {
      console.warn('读取保存的项目ID失败:', error);
      return null;
    }
  };

  // 将项目ID保存到localStorage
  const saveProjectId = (projectId: number) => {
    try {
      localStorage.setItem(PROJECT_STORAGE_KEY, projectId.toString());
    } catch (error) {
      console.warn('保存项目ID失败:', error);
    }
  };
  
  // 加载项目列表
  const fetchProjects = async () => {
    loading.value = true;
    error.value = null;
    
    try {
      const response = await getProjectList();
      
      if (response.success && response.data) {
        projectList.value = response.data;
        
        // 优先尝试恢复之前保存的项目
        const savedProjectId = getSavedProjectId();
        let projectToSelect: Project | null = null;
        
        if (savedProjectId) {
          projectToSelect = projectList.value.find(p => p.id === savedProjectId) || null;
        }
        
        // 如果没有保存的项目或保存的项目不存在，则选择第一个项目
        if (!projectToSelect && projectList.value.length > 0) {
          projectToSelect = projectList.value[0];
        }
        
        // 设置当前项目（如果找到了合适的项目）
        if (projectToSelect) {
          setCurrentProject(projectToSelect);
        }
      } else {
        error.value = response.error || '获取项目列表失败';
      }
    } catch (err) {
      console.error('获取项目列表出错:', err);
      error.value = '获取项目列表时发生错误';
    } finally {
      loading.value = false;
    }
  };
  
  // 设置当前项目
  const setCurrentProject = (project: Project) => {
    currentProject.value = project;
    // 保存到localStorage
    saveProjectId(project.id);
  };
  
  // 根据ID设置当前项目
  const setCurrentProjectById = (projectId: number) => {
    const project = projectList.value.find(p => p.id === projectId);
    if (project) {
      setCurrentProject(project);
    }
  };
  
  return {
    currentProject,
    currentProjectId,
    projectList,
    projectOptions,
    loading,
    error,
    fetchProjects,
    setCurrentProject,
    setCurrentProjectById
  };
});
