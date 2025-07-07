
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/toaster";
import FileOperations from "@/components/FileOperations";
import SqlOperations from "@/components/SqlOperations";
import SystemctlOperations from "@/components/SystemctlOperations";
import DeploymentHistory from "@/components/DeploymentHistory";
import UserManagement from "@/components/UserManagement";
import Header from "@/components/Header";
import { useAuth } from "@/contexts/AuthContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000
    }
  }
});

const Index = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-[#2A4759] text-[#EEEEEE]">
        <Header />
        
        <main className="container mx-auto px-4 py-6">
          <Tabs defaultValue="file" className="w-full">
            <TabsList className={`grid w-full ${isAdmin ? 'grid-cols-5' : 'grid-cols-4'} bg-[#2A4759] mb-6`}>
              <TabsTrigger value="file" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
                File Operations
              </TabsTrigger>
              <TabsTrigger value="sql" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
                SQL Operations
              </TabsTrigger>
              <TabsTrigger value="systemctl" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
                Systemctl Operations
              </TabsTrigger>
              <TabsTrigger value="history" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
                Deployment History
              </TabsTrigger>
              {isAdmin && (
                <TabsTrigger value="users" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
                  User Management
                </TabsTrigger>
              )}
            </TabsList>
            
            <TabsContent value="file" className="p-6 bg-[#1a2b42] rounded-md shadow-lg">
              <FileOperations />
            </TabsContent>
            
            <TabsContent value="sql" className="p-6 bg-[#1a2b42] rounded-md shadow-lg">
              <SqlOperations />
            </TabsContent>
            
            <TabsContent value="systemctl" className="p-6 bg-[#1a2b42] rounded-md shadow-lg">
              <SystemctlOperations />
            </TabsContent>
            
            <TabsContent value="history" className="p-6 bg-[#1a2b42] rounded-md shadow-lg">
              <DeploymentHistory />
            </TabsContent>
            
            {isAdmin && (
              <TabsContent value="users" className="p-6 bg-[#1a2b42] rounded-md shadow-lg">
                <UserManagement />
              </TabsContent>
            )}
          </Tabs>
        </main>
        
        <Toaster />
      </div>
    </QueryClientProvider>
  );
};

export default Index;
