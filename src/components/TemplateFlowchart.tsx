
import React from 'react';
import { Card } from "@/components/ui/card";

interface DeploymentStep {
  type: string;
  description: string;
  order: number;
  ftNumber?: string;
  files?: string[];
  targetVMs?: string[];
  targetUser?: string;
  targetPath?: string;
  service?: string;
  dbConnection?: string;
  dbUser?: string;
  [key: string]: any;
}

interface DeploymentTemplate {
  metadata: {
    ft_number: string;
    generated_at: string;
    description: string;
    total_steps?: number;
  };
  steps: DeploymentStep[];
  dependencies: Array<{
    step: number;
    depends_on: number[];
    parallel: boolean;
  }>;
}

interface TemplateFlowchartProps {
  template: DeploymentTemplate;
}

const TemplateFlowchart: React.FC<TemplateFlowchartProps> = ({ template }) => {
  const getStepIcon = (type: string) => {
    switch (type) {
      case 'file_deployment':
        return '📁';
      case 'ansible_playbook':
        return '⚙️';
      case 'service_restart':
        return '🔄';
      case 'helm_upgrade':
        return '⎈';
      case 'sql_deployment':
        return '🗄️';
      case 'config_change':
        return '⚙️';
      default:
        return '📋';
    }
  };

  const getStepColor = (type: string) => {
    switch (type) {
      case 'file_deployment':
        return 'bg-blue-600';
      case 'ansible_playbook':
        return 'bg-green-600';
      case 'service_restart':
        return 'bg-yellow-600';
      case 'helm_upgrade':
        return 'bg-purple-600';
      case 'sql_deployment':
        return 'bg-red-600';
      case 'config_change':
        return 'bg-orange-600';
      default:
        return 'bg-gray-600';
    }
  };

  const formatStepType = (type: string) => {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="space-y-4 max-h-[500px] overflow-y-auto">
      <div className="text-sm text-[#EEEEEE]/70 mb-4">
        Deployment flow for {template.metadata.ft_number}
        {template.metadata.total_steps && (
          <span className="ml-2 text-[#F79B72]">({template.metadata.total_steps} steps)</span>
        )}
      </div>
      
      {template.steps.map((step, index) => (
        <div key={index} className="relative">
          {/* Connection line to next step */}
          {index < template.steps.length - 1 && (
            <div className="absolute left-6 top-16 w-0.5 h-8 bg-[#F79B72]/50 z-0" />
          )}
          
          {/* Step card */}
          <div className="relative z-10 flex items-start space-x-3">
            {/* Step number and icon */}
            <div className={`flex-shrink-0 w-12 h-12 rounded-full ${getStepColor(step.type)} flex items-center justify-center text-white font-bold text-sm border-2 border-[#EEEEEE]/20`}>
              <span className="text-lg">{getStepIcon(step.type)}</span>
            </div>
            
            {/* Step details */}
            <Card className="flex-1 bg-[#2A4759]/50 border-[#EEEEEE]/20 p-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-[#F79B72] font-medium text-sm">
                    Step {step.order}: {formatStepType(step.type)}
                  </h4>
                  <span className="text-xs text-[#EEEEEE]/50">
                    {step.order === 1 ? 'Start' : `After Step ${step.order - 1}`}
                  </span>
                </div>
                
                <p className="text-xs text-[#EEEEEE]/80 leading-relaxed">
                  {step.description}
                </p>
                
                {/* Step-specific details */}
                <div className="text-xs text-[#EEEEEE]/60 space-y-1">
                  {step.ftNumber && (
                    <div className="text-[#F79B72]">FT: {step.ftNumber}</div>
                  )}
                  
                  {step.type === 'file_deployment' && (
                    <>
                      {step.files && step.files.length > 0 && (
                        <div>Files: {step.files.join(', ')}</div>
                      )}
                      {step.targetVMs && step.targetVMs.length > 0 && (
                        <div>Target VMs: {step.targetVMs.join(', ')}</div>
                      )}
                      {step.targetUser && (
                        <div>Target User: {step.targetUser}</div>
                      )}
                      {step.targetPath && (
                        <div>Target Path: {step.targetPath}</div>
                      )}
                    </>
                  )}
                  
                  {step.type === 'ansible_playbook' && step.playbook && (
                    <div>Playbook: {step.playbook}</div>
                  )}
                  
                  {step.type === 'service_restart' && (
                    <>
                      {step.service && <div>Service: {step.service}</div>}
                      {step.targetVMs && step.targetVMs.length > 0 && (
                        <div>Target VMs: {step.targetVMs.join(', ')}</div>
                      )}
                    </>
                  )}
                  
                  {step.type === 'helm_upgrade' && step.chart && (
                    <div>Chart: {step.chart}</div>
                  )}
                  
                  {step.type === 'sql_deployment' && (
                    <>
                      {step.dbConnection && <div>DB Connection: {step.dbConnection}</div>}
                      {step.dbUser && <div>DB User: {step.dbUser}</div>}
                    </>
                  )}
                </div>
              </div>
            </Card>
          </div>
        </div>
      ))}
      
      {/* Completion indicator */}
      <div className="flex items-center space-x-3 pt-2">
        <div className="flex-shrink-0 w-12 h-12 rounded-full bg-green-600 flex items-center justify-center text-white font-bold border-2 border-[#EEEEEE]/20">
          ✓
        </div>
        <div className="text-sm text-green-400 font-medium">
          Deployment Complete
        </div>
      </div>
    </div>
  );
};

export default TemplateFlowchart;
