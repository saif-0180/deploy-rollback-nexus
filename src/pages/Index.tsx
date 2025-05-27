
import React from 'react';
import FileOperations from '@/components/FileOperations';

const Index = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-[#2A4759] mb-4">DevOps Operations Dashboard</h1>
          <p className="text-xl text-slate-600">Streamlined file deployment and system management</p>
        </div>
        <FileOperations />
      </div>
    </div>
  );
};

export default Index;
