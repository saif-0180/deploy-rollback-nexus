
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useQuery, useMutation } from "@tanstack/react-query";
import LogDisplay from './LogDisplay';
import TemplateFlowchart from './TemplateFlowchart';

interface DeploymentStep {
  type: string;
  description: string;
  order: number;
  [key: string]: any;
}

interface DeploymentTemplate {
  metadata: {
    ft_number: string;
    generated_at: string;
    description: string;
    selectedFiles?: string[];
    selectedVMs?: string[];
    dbConnection?: string;
    dbUser?: string;
    targetUser?: string;
    service?: string;
  };
  steps: DeploymentStep[];
  dependencies: Array<{
    step: number;
    depends_on: number[];
    parallel: boolean;
  }>;
}

const DeployUsingTemplate: React.FC = () => {
  const [selectedFt, setSelectedFt] = useState('');
  const [loadedTemplate, setLoadedTemplate] = useState<DeploymentTemplate | null>(null);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [deploymentStatus, setDeploymentStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed'>('idle');
  const { toast } = useToast();

  // Fetch available templates
  const { data: availableTemplates = [], isLoading: isLoadingTemplates } = useQuery({
    queryKey: ['available-templates'],
    queryFn: async () => {
      const response = await fetch('/api/templates/list');
      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }
      return response.json();
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Load specific template
  const loadTemplateMutation = useMutation({
    mutationFn: async (ftNumber: string) => {
      const response = await fetch(`/api/templates/${ftNumber}`);
      if (!response.ok) {
        throw new Error('Failed to load template');
      }
      return response.json();
    },
    onSuccess: (template) => {
      setLoadedTemplate(template);
      toast({
        title: "Success",
        description: `Template for ${selectedFt} loaded successfully`,
      });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `Failed to load template: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      });
    },
  });

  // Deploy using template
  const deployMutation = useMutation({
    mutationFn: async (template: DeploymentTemplate) => {
      const response = await fetch('/api/deploy/template', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ft_number: template.metadata.ft_number,
          template: template
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to start template deployment');
      }
      return response.json();
    },
    onSuccess: (data) => {
      setDeploymentId(data.deploymentId);
      setDeploymentStatus('running');
      toast({
        title: "Deployment Started",
        description: `Template deployment initiated with ID: ${data.deploymentId}`,
      });
    },
    onError: (error) => {
      setDeploymentStatus('failed');
      toast({
        title: "Deployment Failed",
        description: `Failed to start deployment: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      });
    },
  });

  // Fetch deployment logs
  const { data: deploymentLogs } = useQuery({
    queryKey: ['template-deployment-logs', deploymentId],
    queryFn: async () => {
      if (!deploymentId) return { logs: [], status: 'idle' };
      
      const response = await fetch(`/api/deploy/template/${deploymentId}/logs`);
      if (!response.ok) {
        throw new Error('Failed to fetch deployment logs');
      }
      return response.json();
    },
    enabled: !!deploymentId,
    refetchInterval: 2000, // Poll every 2 seconds
  });

  // Update logs and status from API
  useEffect(() => {
    if (deploymentLogs) {
      setLogs(deploymentLogs.logs || []);
      setDeploymentStatus(deploymentLogs.status || 'idle');
    }
  }, [deploymentLogs]);

  const handleLoadTemplate = () => {
    if (!selectedFt) {
      toast({
        title: "Error",
        description: "Please select an FT number",
        variant: "destructive",
      });
      return;
    }
    loadTemplateMutation.mutate(selectedFt);
  };

  const handleDeploy = () => {
    if (!loadedTemplate) {
      toast({
        title: "Error",
        description: "Please load a template first",
        variant: "destructive",
      });
      return;
    }
    deployMutation.mutate(loadedTemplate);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Deploy using Template</h2>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left Column - Template Selection and Controls */}
        <div className="xl:col-span-1 space-y-6">
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Template Selection</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
                <Select value={selectedFt} onValueChange={setSelectedFt}>
                  <SelectTrigger id="ft-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder={isLoadingTemplates ? "Loading..." : "Select an FT"} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTemplates.map((ft: string) => (
                      <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={handleLoadTemplate}
                disabled={!selectedFt || loadTemplateMutation.isPending}
                className="w-full bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80 border-[#EEEEEE]/30"
              >
                {loadTemplateMutation.isPending ? "Loading Template..." : "Load Template"}
              </Button>

              {loadedTemplate && (
                <div className="mt-4 p-3 bg-[#2A4759]/50 rounded-md">
                  <h4 className="text-[#F79B72] font-medium mb-2">Template Info</h4>
                  <div className="text-sm text-[#EEEEEE] space-y-1">
                    <div>FT: {loadedTemplate.metadata.ft_number}</div>
                    <div>Steps: {loadedTemplate.steps.length}</div>
                    <div>Generated: {new Date(loadedTemplate.metadata.generated_at).toLocaleString()}</div>
                    {loadedTemplate.metadata.selectedVMs && (
                      <div>VMs: {loadedTemplate.metadata.selectedVMs.join(', ')}</div>
                    )}
                    {loadedTemplate.metadata.targetUser && (
                      <div>Target User: {loadedTemplate.metadata.targetUser}</div>
                    )}
                  </div>
                </div>
              )}

              <Button
                onClick={handleDeploy}
                disabled={!loadedTemplate || deployMutation.isPending || deploymentStatus === 'running'}
                className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              >
                {deployMutation.isPending || deploymentStatus === 'running' ? "Deploying..." : "Deploy"}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Middle Column - Flowchart */}
        <div className="xl:col-span-1">
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30 h-full">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Deployment Flow</CardTitle>
            </CardHeader>
            <CardContent>
              {loadedTemplate ? (
                <TemplateFlowchart template={loadedTemplate} />
              ) : (
                <div className="flex items-center justify-center h-[500px] text-[#EEEEEE]/50">
                  Load a template to see the deployment flow
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Logs */}
        <div className="xl:col-span-1">
          <LogDisplay
            logs={logs}
            height="838px"
            fixedHeight={true}
            title="Template Deployment Logs"
            status={deploymentStatus}
          />
        </div>
      </div>
    </div>
  );
};

export default DeployUsingTemplate;
