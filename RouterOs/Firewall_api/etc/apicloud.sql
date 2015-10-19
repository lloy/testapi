drop database if exists apicloud;
create database apicloud;

use apicloud;

drop table if exists tasks; 
create table tasks(
    task_id varchar(40) NOT NULL,
	create_time DATETIME NOT NULL,
    template_type varchar(16) NOT NULL,
    model_type varchar(16) NOT NULL,
    status varchar(16) NOT NULL,
    instances_num INT UNSIGNED NOT NULL,
	PRIMARY KEY (task_id)
);

drop table if exists instances; 
create table instances(
    instance_uuid varchar(40) NOT NULL,
    task_id varchar(40) NOT NULL,
    name varchar(40) NOT NULL,
    ip varchar(40) NOT NULL,
    status varchar(40) NOT NULL,
    os_type varchar(40) NOT NULL,
    username varchar(40) NOT NULL,
    passwd varchar(40) NOT NULL,
    template_type varchar(16) NOT NULL,
    instance_type varchar(16) NOT NULL,
    iaas_type varchar(16) NOT NULL,
    customers varchar(16) NOT NULL,
	create_time DATETIME NOT NULL,
    online_time DATETIME NOT NULL,
    off_time DATETIME,
	PRIMARY KEY (instance_uuid)
);

drop table if exists instancetype; 
create table instancetype(
    name varchar(24) NOT NULL,
    core_num INT UNSIGNED NOT NULL,
    ram INT UNSIGNED NOT NULL,
    disk INT UNSIGNED NOT NULL,
    extend_disk INT UNSIGNED NOT NULL,
    PRIMARY KEY (name)
);

drop table if exists templatetype; 
create table templatetype(
    name varchar(24) NOT NULL,
    iaas_type varchar(24) NOT NULL,
    PRIMARY KEY (name)
);


drop table if exists iptable; 
create table iptable(
    ipaddress varchar(24) NOT NULL,
    vlan_id INT UNSIGNED,
    is_alloc TINYINT(1) NOT NULL,
    PRIMARY KEY(ipaddress)
);
